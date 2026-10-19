"""Scheme service — eligibility engine + search."""
import json
import math
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemes import (
    BenefitOut, DocumentRequirementOut, EligibilityRequest, EligibilityResult, EligibilityRuleOut,
    RuleResult, SchemeDetail, SchemeListItem, SchemeListResponse,
)

logger = structlog.get_logger(__name__)



def _as_json(value: Any) -> Any:
    """eligibility_rule.value is jsonb; some drivers hand it back as text."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def evaluate_rule(rule: dict, profile: dict) -> str:
    """Evaluate one eligibility rule against a profile -> PASS | FAIL | UNKNOWN.

    Missing profile data is UNKNOWN (never assumed). Pure function: no I/O.
    """
    operator = rule["operator"]
    threshold = _as_json(rule["value"])
    citizen_val = profile.get(rule["attribute"])
    if citizen_val is None:
        return "UNKNOWN"
    try:
        if operator == "=":
            return "PASS" if str(citizen_val).lower() == str(threshold).lower() else "FAIL"
        if operator == "!=":
            return "PASS" if str(citizen_val).lower() != str(threshold).lower() else "FAIL"
        if operator == ">=":
            return "PASS" if float(citizen_val) >= float(threshold) else "FAIL"
        if operator == ">":
            return "PASS" if float(citizen_val) > float(threshold) else "FAIL"
        if operator == "<=":
            return "PASS" if float(citizen_val) <= float(threshold) else "FAIL"
        if operator == "<":
            return "PASS" if float(citizen_val) < float(threshold) else "FAIL"
        if operator in ("IN", "NOT_IN"):
            vals = [str(v).lower() for v in (threshold if isinstance(threshold, list) else [threshold])]
            member = str(citizen_val).lower() in vals
            return "PASS" if member == (operator == "IN") else "FAIL"
        if operator == "IS_TRUE":
            return "PASS" if bool(citizen_val) else "FAIL"
        if operator == "IS_FALSE":
            return "PASS" if not bool(citizen_val) else "FAIL"
        if operator == "BETWEEN":
            lo, hi = float(threshold[0]), float(threshold[1])
            return "PASS" if lo <= float(citizen_val) <= hi else "FAIL"
    except (TypeError, ValueError, IndexError):
        return "UNKNOWN"
    return "UNKNOWN"


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
        verification_status: Optional[str] = None,
    ) -> SchemeListResponse:
        conditions = ["s.status = :status"]
        params: dict[str, Any] = {"status": status}

        if q:
            conditions.append(
                "(s.scheme_name ILIKE :q OR s.short_description ILIKE :q OR s.name_ta ILIKE :q OR "
                "s.tsv @@ websearch_to_tsquery('simple', :q_tsq))"
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

        if verification_status:
            conditions.append("s.verification_status = :vstatus")
            params["vstatus"] = verification_status

        where = " AND ".join(conditions)

        count_r = await self.db.execute(
            text(f"SELECT count(*) FROM schemes.scheme s WHERE {where}"), params
        )
        total = count_r.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(
            text(f"""
                SELECT s.scheme_id, s.scheme_code, s.scheme_name AS name, s.name_ta,
                       s.short_description AS description, d.department_name, s.category,
                       s.scheme_level, s.status, s.effective_from, s.effective_to,
                       s.verified_at, sr.url AS source_url,
                       s.verification_status, s.source_document_ref
                FROM schemes.scheme s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                WHERE {where}
                ORDER BY s.scheme_name
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": offset},
        )
        items = [SchemeListItem(**row._mapping) for row in result.fetchall()]
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
                SELECT s.scheme_id, s.scheme_code, s.scheme_name AS name, s.name_ta,
                       s.short_description AS description, d.department_name, s.category,
                       s.scheme_level, s.status, s.effective_from, s.effective_to,
                       s.verified_at, sr.url AS source_url,
                       s.verification_status, s.source_document_ref,
                       s.application_url, s.official_url AS official_source_url,
                       s.full_description, s.benefits_summary, NULL::text AS notes
                FROM schemes.scheme s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                WHERE s.scheme_id = :sid
            """),
            {"sid": scheme_id},
        )
        row = r.fetchone()
        if not row:
            return None

        scheme = SchemeDetail(**row._mapping)

        # Benefits
        br = await self.db.execute(
            text("""
                SELECT benefit_id, benefit_type, description, amount::float AS amount,
                       currency AS unit
                FROM schemes.benefit WHERE scheme_id = :sid
            """),
            {"sid": scheme_id},
        )
        scheme.benefits = [BenefitOut(**b._mapping) for b in br.fetchall()]

        # Eligibility rules
        er = await self.db.execute(
            text("""
                SELECT rule_id, rule_group, attribute, operator, value,
                       unit, mandatory, human_readable, human_readable_ta, source_reference
                FROM schemes.eligibility_rule
                WHERE scheme_id = :sid
                  AND (effective_from IS NULL OR effective_from <= CURRENT_DATE)
                  AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                ORDER BY rule_group, attribute
            """),
            {"sid": scheme_id},
        )
        scheme.eligibility_rules = [EligibilityRuleOut(**e._mapping) for e in er.fetchall()]

        # Document requirements
        dr = await self.db.execute(
            text("""
                SELECT document_requirement_id AS requirement_id, document_name AS document_type,
                       description, mandatory
                FROM schemes.document_requirement WHERE scheme_id = :sid
            """),
            {"sid": scheme_id},
        )
        scheme.required_documents = [DocumentRequirementOut(**d._mapping) for d in dr.fetchall()]

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
            raise LookupError("Scheme not found")

        rules = [r.model_dump() for r in scheme.eligibility_rules]
        profile_dict = profile.model_dump(exclude_none=False)

        # Compute age from DOB if not provided directly
        # (profile.age may come from citizen_profile.date_of_birth)

        rule_results: list[RuleResult] = []
        missing_attrs: list[str] = []
        failing_rules: list[str] = []

        # Group rules: AND within group, OR across groups
        groups: dict[int, list] = {}
        for rule in rules:
            g = rule.get("rule_group", 1)
            groups.setdefault(g, []).append(rule)

        group_results: list[str] = []  # PASS | FAIL | UNKNOWN per group

        for group_rules in groups.values():
            g_outcomes = []
            for rule in group_rules:
                outcome = evaluate_rule(rule, profile_dict)
                attr = rule["attribute"]
                rr = RuleResult(
                    rule_id=rule["rule_id"],
                    attribute=attr,
                    operator=rule["operator"],
                    threshold=rule["value"],
                    citizen_value=profile_dict.get(attr),
                    outcome=outcome,
                    reason=rule.get("human_readable") or "",
                    mandatory=rule.get("mandatory", True),
                )
                rule_results.append(rr)

                if rule.get("mandatory", True):
                    g_outcomes.append(outcome)
                    if outcome == "UNKNOWN":
                        missing_attrs.append(attr)
                    elif outcome == "FAIL":
                        failing_rules.append(rule.get("human_readable") or attr)

            # Group: any FAIL → FAIL; any UNKNOWN (or nothing evaluated) → UNKNOWN; else PASS
            if not g_outcomes:
                group_results.append("UNKNOWN")
            elif "FAIL" in g_outcomes:
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
            verification_status=scheme.verification_status,
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
