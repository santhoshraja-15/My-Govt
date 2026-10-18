"""Scheme service — eligibility engine + search."""
import math
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemes import (
    EligibilityRequest, EligibilityResult, RuleResult,
    SchemeDetail, SchemeListItem, SchemeListResponse,
)

logger = structlog.get_logger(__name__)


class SchemeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_schemes(
        self,
        q: Optional[str],
        department_id: Optional[int],
        category: Optional[str],
        level: Optional[str],
        status: str,
        page: int,
        page_size: int,
    ) -> SchemeListResponse:
        conditions = ["s.status = :status"]
        params: dict[str, Any] = {"status": status}

        if q:
            conditions.append(
                "(s.name ILIKE :q OR s.description ILIKE :q OR "
                "to_tsvector('simple', coalesce(s.name,'') || ' ' || coalesce(s.description,'')) "
                "@@ websearch_to_tsquery('simple', :q_tsq))"
            )
            params["q"] = f"%{q}%"
            params["q_tsq"] = q

        if department_id:
            conditions.append("s.department_id = :dept_id")
            params["dept_id"] = department_id

        if category:
            conditions.append("s.category = :category")
            params["category"] = category

        if level:
            conditions.append("s.scheme_level = :level")
            params["level"] = level

        where = " AND ".join(conditions)

        count_r = await self.db.execute(
            text(f"SELECT count(*) FROM schemes.scheme s WHERE {where}"), params
        )
        total = count_r.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            text(f"""
                SELECT s.scheme_id, s.scheme_code, s.name, s.name_ta,
                       s.description, d.department_name, s.category,
                       s.scheme_level, s.status, s.effective_from, s.effective_to,
                       s.verified_at, sr.url AS source_url
                FROM schemes.scheme s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                WHERE {where}
                ORDER BY s.name
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": offset},
        )
        cols = list(result.keys())
        items = [
            SchemeListItem(**dict(zip(cols, row)))
            for row in result.fetchall()
        ]
        return SchemeListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_scheme(self, scheme_id: UUID) -> Optional[SchemeDetail]:
        r = await self.db.execute(
            text("""
                SELECT s.scheme_id, s.scheme_code, s.name, s.name_ta,
                       s.description, d.department_name, s.category,
                       s.scheme_level, s.status, s.effective_from, s.effective_to,
                       s.verified_at, sr.url AS source_url,
                       s.application_url, s.official_source_url, s.notes
                FROM schemes.scheme s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                WHERE s.scheme_id = :sid
            """),
            {"sid": str(scheme_id)},
        )
        row = r.fetchone()
        if not row:
            return None

        scheme = SchemeDetail(**dict(zip(r.keys(), row)))

        # Benefits
        br = await self.db.execute(
            text("SELECT * FROM schemes.benefit WHERE scheme_id = :sid"),
            {"sid": str(scheme_id)},
        )
        scheme.benefits = [dict(zip(br.keys(), b)) for b in br.fetchall()]

        # Eligibility rules
        er = await self.db.execute(
            text("""
                SELECT rule_id, rule_group, attribute, operator, value,
                       unit, mandatory, human_readable, human_readable_ta, source_reference
                FROM schemes.eligibility_rule
                WHERE scheme_id = :sid AND status = 'active'
                ORDER BY rule_group, attribute
            """),
            {"sid": str(scheme_id)},
        )
        scheme.eligibility_rules = [dict(zip(er.keys(), e)) for e in er.fetchall()]

        # Document requirements
        dr = await self.db.execute(
            text("SELECT * FROM schemes.document_requirement WHERE scheme_id = :sid"),
            {"sid": str(scheme_id)},
        )
        scheme.required_documents = [dict(zip(dr.keys(), d)) for d in dr.fetchall()]

        return scheme

    async def check_eligibility(
        self,
        scheme_id: UUID,
        profile: EligibilityRequest,
        current_user: Any,
    ) -> EligibilityResult:
        """Deterministic eligibility evaluation — no LLM involved."""
        scheme = await self.get_scheme(scheme_id)
        if not scheme:
            raise ValueError("Scheme not found")

        rules = scheme.eligibility_rules
        profile_dict = profile.model_dump(exclude_none=False)

        # Compute age from DOB if not provided directly
        # (profile.age may come from citizen_profile.date_of_birth)

        rule_results: list[RuleResult] = []
        missing_attrs: list[str] = []
        failing_rules: list[str] = []

        def _evaluate_rule(rule: dict) -> str:
            attr = rule["attribute"]
            operator = rule["operator"]
            threshold = rule["value"]
            citizen_val = profile_dict.get(attr)

            if citizen_val is None:
                return "UNKNOWN"

            try:
                if operator == "=":
                    return "PASS" if str(citizen_val) == str(threshold) else "FAIL"
                elif operator == "!=":
                    return "PASS" if str(citizen_val) != str(threshold) else "FAIL"
                elif operator == ">=":
                    return "PASS" if float(citizen_val) >= float(threshold) else "FAIL"
                elif operator == ">":
                    return "PASS" if float(citizen_val) > float(threshold) else "FAIL"
                elif operator == "<=":
                    return "PASS" if float(citizen_val) <= float(threshold) else "FAIL"
                elif operator == "<":
                    return "PASS" if float(citizen_val) < float(threshold) else "FAIL"
                elif operator == "IN":
                    vals = threshold if isinstance(threshold, list) else [threshold]
                    return "PASS" if str(citizen_val).lower() in [str(v).lower() for v in vals] else "FAIL"
                elif operator == "NOT_IN":
                    vals = threshold if isinstance(threshold, list) else [threshold]
                    return "PASS" if str(citizen_val).lower() not in [str(v).lower() for v in vals] else "FAIL"
                elif operator == "IS_TRUE":
                    return "PASS" if bool(citizen_val) else "FAIL"
                elif operator == "IS_FALSE":
                    return "PASS" if not bool(citizen_val) else "FAIL"
                elif operator == "BETWEEN":
                    lo, hi = float(threshold[0]), float(threshold[1])
                    return "PASS" if lo <= float(citizen_val) <= hi else "FAIL"
                else:
                    return "UNKNOWN"
            except (TypeError, ValueError):
                return "UNKNOWN"

        # Group rules: AND within group, OR across groups
        groups: dict[int, list] = {}
        for rule in rules:
            g = rule.get("rule_group", 1)
            groups.setdefault(g, []).append(rule)

        group_results: list[str] = []  # PASS | FAIL | UNKNOWN per group

        for group_id, group_rules in groups.items():
            g_outcomes = []
            for rule in group_rules:
                outcome = _evaluate_rule(rule)
                attr = rule["attribute"]
                rr = RuleResult(
                    rule_id=rule["rule_id"],
                    attribute=attr,
                    operator=rule["operator"],
                    threshold=rule["value"],
                    citizen_value=profile_dict.get(attr),
                    outcome=outcome,
                    reason=rule.get("human_readable", ""),
                    mandatory=rule.get("mandatory", True),
                )
                rule_results.append(rr)

                if rule.get("mandatory", True):
                    g_outcomes.append(outcome)
                    if outcome == "UNKNOWN":
                        missing_attrs.append(attr)
                    elif outcome == "FAIL":
                        failing_rules.append(rule.get("human_readable", attr))

            # Group: any FAIL → FAIL; any UNKNOWN → UNKNOWN; else PASS
            if "FAIL" in g_outcomes:
                group_results.append("FAIL")
            elif "UNKNOWN" in g_outcomes:
                group_results.append("UNKNOWN")
            else:
                group_results.append("PASS")

        # Across groups (OR): any PASS → ELIGIBLE
        if "PASS" in group_results:
            overall = "ELIGIBLE"
        elif "UNKNOWN" in group_results or not group_results:
            overall = "INSUFFICIENT_DATA"
        else:
            overall = "NOT_ELIGIBLE"

        return EligibilityResult(
            scheme_id=scheme_id,
            scheme_name=scheme.name,
            overall=overall,
            rule_results=rule_results,
            missing_attributes=list(set(missing_attrs)),
            failing_rules=failing_rules,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def get_categories(self) -> list:
        r = await self.db.execute(text(
            "SELECT DISTINCT category FROM schemes.scheme WHERE category IS NOT NULL ORDER BY category"
        ))
        return [row[0] for row in r.fetchall()]
