"""AI Chat service — hybrid retrieval, trust engine, LLM orchestration."""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, Citation, ConversationOut

logger = structlog.get_logger(__name__)

# Intent classification (keyword-based fallback when LLM unavailable)
_INTENT_PATTERNS = {
    "scheme_search": ["scheme", "yojana", "benefit", "subsidy", "eligible", "apply", "திட்டம்"],
    "service_lookup": ["service", "certificate", "apply for", "e-sevai", "சேவை"],
    "complaint_status": ["complaint", "status", "reference", "MYG-", "புகார்"],
    "policy_query": ["policy", "law", "act", "order", "GO ", "நடைமுறை"],
    "location_info": ["office", "taluk", "district", "address", "near", "அலுவலகம்"],
    "eligibility_check": ["am i eligible", "qualify", "criteria", "தகுதி"],
}


def _classify_intent(message: str) -> str:
    msg_lower = message.lower()
    scores: dict[str, int] = {}
    for intent, keywords in _INTENT_PATTERNS.items():
        scores[intent] = sum(1 for kw in keywords if kw.lower() in msg_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general_query"


def _detect_language(message: str) -> str:
    """Detect Tamil or English."""
    tamil_chars = sum(1 for c in message if "\u0B80" <= c <= "\u0BFF")
    return "ta" if tamil_chars > 2 else "en"



_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from get give has have how i in is it me my of on or "
    "please tell the to what when where which who why will with you your about any there their "
    "this that these those should would could".split()
)

# Weight applied to a source's reliability when computing answer trust.
VERIFICATION_WEIGHT = {
    "official_verified": 1.0,
    "externally_referenced": 0.6,
    "provisional": 0.5,
    "unverified": 0.3,
}


def build_tsquery(message: str, max_terms: int = 8) -> Optional[str]:
    """OR-query of the meaningful words in a question ('a | b | c'), or None.

    Only letters/digits (incl. Tamil) survive, so the result is safe for to_tsquery().
    """
    seen: list[str] = []
    for tok in re.findall(r"[\w\u0B80-\u0BFF]+", message.lower()):
        if len(tok) >= 3 and tok not in _STOPWORDS and tok not in seen:
            seen.append(tok)
    return " | ".join(seen[:max_terms]) or None


def compute_trust(retrieved: list[dict]) -> float:
    """Mean of reliability x verification weight; 0.0 when nothing was retrieved."""
    if not retrieved:
        return 0.0
    scores = [
        float(r.get("reliability_score") or 0.5)
        * VERIFICATION_WEIGHT.get(r.get("verification_status") or "provisional", 0.3)
        for r in retrieved
    ]
    return round(sum(scores) / len(scores), 3)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_message(self, request: ChatRequest, current_user) -> ChatResponse:
        message_id = uuid.uuid4()
        conversation_id = request.conversation_id or uuid.uuid4()
        citizen_id = getattr(current_user, "citizen_id", None) if current_user else None

        if citizen_id:
            await self._ensure_conversation(conversation_id, citizen_id)

        intent = _classify_intent(request.message)
        language = request.language if request.language in ("en", "ta") else _detect_language(request.message)

        retrieved = await self._hybrid_retrieve(request.message, intent, limit=8)
        context_text, citations = self._build_context(retrieved)
        trust_score = self._compute_trust(retrieved)
        contains_unverified = any(c.verification_status != "official_verified" for c in citations)

        answer, abstained, abstain_reason, degraded = await self._generate_answer(
            request.message, intent, context_text, language, trust_score, contains_unverified
        )
        actions = self._suggest_actions(intent)

        decision_id = uuid.uuid4()
        await self._save_decision(
            decision_id, citizen_id, conversation_id if citizen_id else None,
            {"query": request.message, "intent": intent, "language": language,
             "retrieved_count": len(retrieved), "degraded": degraded,
             "contains_unverified": contains_unverified},
            trust_score, abstained, retrieved,
        )
        if citizen_id:
            await self._save_messages(conversation_id, message_id, request.message, answer, language)

        return ChatResponse(
            message_id=message_id,
            conversation_id=conversation_id,
            answer=answer,
            intent=intent,
            language=language,
            citations=citations,
            trust_score=trust_score,
            abstained=abstained,
            abstain_reason=abstain_reason,
            decision_id=decision_id,
            action_type="inform",
            suggested_actions=actions,
            degraded=degraded,
            contains_unverified=contains_unverified,
        )

    async def _hybrid_retrieve(self, query: str, intent: str, limit: int = 8) -> list[dict]:
        """Keyword retrieval over curated tables (vector search joins in once embeddings exist).

        Deprecated records are never retrieved. Provisional / externally-referenced records are
        returned WITH their verification_status so callers can label them.
        """
        tsq = build_tsquery(query)
        if tsq is None:
            return []
        results: list[dict] = []

        if intent in ("scheme_search", "eligibility_check", "general_query"):
            r = await self.db.execute(
                text("""
                    SELECT s.scheme_id::text AS entity_id, s.scheme_name AS title,
                           s.short_description AS description, d.department_name,
                           'scheme' AS entity_type, s.verified_at::text AS verified_at,
                           coalesce(s.official_url, sr.url) AS source_url,
                           sr.reliability_score::float AS reliability_score,
                           s.verification_status, s.source_document_ref
                    FROM schemes.scheme s
                    LEFT JOIN administration.department d ON d.department_id = s.department_id
                    LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                    WHERE s.status = 'active' AND s.verification_status <> 'deprecated'
                      AND s.tsv @@ to_tsquery('simple', :tsq)
                    ORDER BY ts_rank(s.tsv, to_tsquery('simple', :tsq)) DESC, s.scheme_name
                    LIMIT :lim
                """),
                {"tsq": tsq, "lim": limit},
            )
            results.extend(dict(row._mapping) for row in r.fetchall())

        if intent in ("service_lookup", "general_query"):
            r = await self.db.execute(
                text("""
                    SELECT s.service_id::text AS entity_id, s.service_name AS title,
                           s.description, d.department_name,
                           'service' AS entity_type, s.verified_at::text AS verified_at,
                           coalesce(s.official_url, s.application_url, sr.url) AS source_url,
                           sr.reliability_score::float AS reliability_score,
                           s.verification_status, s.source_document_ref
                    FROM services.service s
                    LEFT JOIN administration.department d ON d.department_id = s.department_id
                    LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                    WHERE s.status = 'active' AND s.verification_status <> 'deprecated'
                      AND to_tsvector('simple', coalesce(s.service_name,'') || ' ' || coalesce(s.description,''))
                          @@ to_tsquery('simple', :tsq)
                    ORDER BY s.service_name
                    LIMIT :lim
                """),
                {"tsq": tsq, "lim": limit},
            )
            results.extend(dict(row._mapping) for row in r.fetchall())

        if intent in ("policy_query", "general_query"):
            r = await self.db.execute(
                text("""
                    SELECT d.document_id::text AS entity_id, d.title,
                           substring(d.full_text, 1, 500) AS description,
                           dep.department_name, 'document' AS entity_type,
                           NULL::text AS verified_at, d.source_url,
                           sr.reliability_score::float AS reliability_score,
                           'unverified' AS verification_status,
                           d.source_url AS source_document_ref
                    FROM documents.document d
                    LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                    LEFT JOIN system.source_registry sr ON sr.source_id = d.source_id
                    WHERE d.status = 'active'
                      AND to_tsvector('simple', coalesce(d.title,'') || ' ' || coalesce(d.full_text,''))
                          @@ to_tsquery('simple', :tsq)
                    LIMIT :lim
                """),
                {"tsq": tsq, "lim": max(limit // 2, 1)},
            )
            results.extend(dict(row._mapping) for row in r.fetchall())

        return results[:limit]

    def _build_context(self, retrieved: list[dict]) -> tuple[str, list[Citation]]:
        citations: list[Citation] = []
        context_parts: list[str] = []
        for i, item in enumerate(retrieved, 1):
            status = item.get("verification_status") or "unverified"
            title = item.get("title", "")
            description = item.get("description") or ""
            dept = item.get("department_name") or ""
            context_parts.append(
                f"[{i}] **{title}** ({dept}) [{status}]\n{description[:400]}"
            )
            citations.append(Citation(
                index=i,
                title=title,
                department=dept or None,
                source_url=item.get("source_url"),
                verified_at=str(item["verified_at"]) if item.get("verified_at") else None,
                verification_status=status,
                source_document_ref=item.get("source_document_ref"),
            ))
        return "\n\n".join(context_parts), citations

    def _compute_trust(self, retrieved: list[dict]) -> float:
        return compute_trust(retrieved)

    async def _generate_answer(
        self, query: str, intent: str, context: str,
        language: str, trust_score: float, contains_unverified: bool = True,
    ) -> tuple[str, bool, Optional[str], bool]:
        """LLM answer grounded in `context`, or a deterministic template. Abstains with no context."""
        if not context:
            msg = (
                "I couldn't find verified information to answer your question reliably. "
                "Please visit the official Tamil Nadu government portal at https://www.tn.gov.in "
                "or contact your nearest e-Sevai centre."
            )
            return msg, True, "no_supporting_sources", False

        if settings.LLM_PROVIDER != "none" and settings.LLM_API_KEY:
            try:
                answer = await self._call_llm(query, context, language)
                return answer, False, None, False
            except Exception as e:
                logger.warning("LLM call failed, using template", error=str(e))

        answer = self._template_answer(query, intent, context, language, contains_unverified)
        return answer, False, None, True

    async def _call_llm(self, query: str, context: str, language: str) -> str:
        system_prompt = (
            "You are MyGovt Assistant, a trusted AI for Tamil Nadu government services. "
            "Answer ONLY from the provided context. If the answer is not in the context, say you don't know. "
            "Never invent government facts, scheme names, amounts, or eligibility criteria. "
            f"Respond in {'Tamil' if language == 'ta' else 'English'}."
        )
        prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"

        if settings.LLM_PROVIDER == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            return resp.choices[0].message.content or ""

        elif settings.LLM_PROVIDER == "google":
            import google.generativeai as genai
            genai.configure(api_key=settings.LLM_API_KEY)
            model = genai.GenerativeModel(settings.LLM_MODEL)
            resp = await model.generate_content_async(f"{system_prompt}\n\n{prompt}")
            return resp.text or ""

        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")

    def _template_answer(self, query: str, intent: str, context: str, language: str,
                         contains_unverified: bool = True) -> str:
        if not context:
            if language == "ta":
                return "மன்னிக்கவும், இந்தக் கேள்விக்கான சரிபார்க்கப்பட்ட தகவல் கிடைக்கவில்லை."
            return ("I found limited verified information for your query. "
                    "Please check https://www.tn.gov.in or your nearest e-Sevai centre.")
        if contains_unverified:
            intro = ("Here is what I found. Items marked [provisional], [unverified] or "
                     "[externally_referenced] have NOT been confirmed against an official document:\n")
            closing = "\n\n*Please confirm details with the respective department portal before acting.*"
        else:
            intro = "Based on records verified against official sources, here is what I found:\n"
            closing = "\n\n*For official confirmation, please visit the respective department portal.*"
        return "\n".join([intro, context[:1500], closing])

    def _suggest_actions(self, intent: str) -> list[str]:
        mapping = {
            "scheme_search": ["Browse all schemes", "Check eligibility", "Contact department"],
            "service_lookup": ["Apply online", "Find nearest e-Sevai", "Download forms"],
            "complaint_status": ["Track complaint", "File new complaint"],
            "policy_query": ["Download document", "Contact department"],
            "eligibility_check": ["Check eligibility", "Update profile"],
        }
        return mapping.get(intent, ["Browse services", "Contact us"])

    # -- persistence: each write runs in a savepoint so one failure cannot poison the request --
    async def _ensure_conversation(self, conversation_id: UUID, citizen_id) -> None:
        try:
            async with self.db.begin_nested():
                await self.db.execute(
                    text("""
                        INSERT INTO ai.conversation (conversation_id, citizen_id)
                        VALUES (:cid, :uid) ON CONFLICT (conversation_id) DO NOTHING
                    """),
                    {"cid": conversation_id, "uid": citizen_id},
                )
            await self.db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("conversation_persist_failed", error=str(e))

    async def _save_messages(self, conv_id, msg_id, user_msg, answer, language) -> None:
        try:
            async with self.db.begin_nested():
                await self.db.execute(
                    text("""
                        INSERT INTO ai.message (message_id, conversation_id, role, content, language)
                        SELECT CAST(:u AS uuid), CAST(:cid AS uuid), 'user', CAST(:content AS text), CAST(:lang AS text)
                        WHERE EXISTS (SELECT 1 FROM ai.conversation WHERE conversation_id = :cid)
                        UNION ALL
                        SELECT CAST(:a AS uuid), CAST(:cid AS uuid), 'assistant', CAST(:answer AS text), CAST(:lang AS text)
                        WHERE EXISTS (SELECT 1 FROM ai.conversation WHERE conversation_id = :cid)
                    """),
                    {"u": uuid.uuid4(), "a": msg_id, "cid": conv_id, "content": user_msg,
                     "answer": answer, "lang": language},
                )
            await self.db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("messages_persist_failed", error=str(e))

    async def _save_decision(self, decision_id: UUID, citizen_id, conversation_id, result: dict,
                             trust_score: float, abstained: bool, retrieved: list[dict]) -> None:
        """ai.decision + one ai.decision_lineage row per source actually used."""
        try:
            async with self.db.begin_nested():
                await self.db.execute(
                    text("""
                        INSERT INTO ai.decision (decision_id, citizen_id, conversation_id, decision_type,
                                                 result, confidence_score, abstained, prompt_version)
                        VALUES (:did, :cit, :conv, 'information_answer',
                                CAST(:result AS jsonb), :conf, :abst, 'chat-v1')
                    """),
                    {"did": decision_id, "cit": citizen_id, "conv": conversation_id,
                     "result": json.dumps(result), "conf": min(trust_score, 1.0), "abst": abstained},
                )
                for item in retrieved:
                    await self.db.execute(
                        text("""
                            INSERT INTO ai.decision_lineage
                                (decision_id, source_type, source_id, source_reference, reason, contribution)
                            VALUES (:did, :stype, :sid, :sref, :reason, 'supports')
                        """),
                        {"did": decision_id, "stype": item.get("entity_type", "unknown"),
                         "sid": str(item.get("entity_id")), "sref": item.get("source_document_ref"),
                         "reason": f"retrieved; verification_status={item.get('verification_status')}"},
                    )
            await self.db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("decision_persist_failed", error=str(e))

    async def get_conversations(self, citizen_id) -> list:
        if citizen_id is None:
            return []
        r = await self.db.execute(
            text("""
                SELECT c.conversation_id, c.started_at AS created_at,
                       max(m.created_at) AS last_message_at,
                       count(m.message_id)::int AS message_count,
                       (SELECT content FROM ai.message WHERE conversation_id = c.conversation_id
                        AND role = 'user' ORDER BY created_at DESC LIMIT 1) AS preview
                FROM ai.conversation c
                LEFT JOIN ai.message m ON m.conversation_id = c.conversation_id
                WHERE c.citizen_id = :cid
                GROUP BY c.conversation_id, c.started_at
                ORDER BY coalesce(max(m.created_at), c.started_at) DESC
                LIMIT 50
            """),
            {"cid": citizen_id},
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_messages(self, conversation_id: UUID, current_user) -> Optional[list]:
        """Messages of a conversation the caller owns; None if absent or not theirs."""
        citizen_id = getattr(current_user, "citizen_id", None) if current_user else None
        if citizen_id is None:
            return None
        own = await self.db.execute(
            text("SELECT 1 FROM ai.conversation WHERE conversation_id = :cid AND citizen_id = :uid"),
            {"cid": conversation_id, "uid": citizen_id},
        )
        if not own.fetchone():
            return None
        r = await self.db.execute(
            text("""
                SELECT message_id, role, content, created_at
                FROM ai.message WHERE conversation_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": conversation_id},
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_decision_lineage(self, decision_id: UUID, current_user=None) -> Optional[dict]:
        """Sources behind an answer. Anonymous decisions are readable by id; owned ones owner/admin only."""
        r = await self.db.execute(
            text("""
                SELECT decision_id, citizen_id, decision_type, result,
                       confidence_score::float AS confidence_score, abstained, created_at
                FROM ai.decision WHERE decision_id = :did
            """),
            {"did": decision_id},
        )
        d = r.fetchone()
        if not d:
            return None
        if d.citizen_id is not None:
            caller = getattr(current_user, "citizen_id", None) if current_user else None
            role = getattr(current_user, "role", "") if current_user else ""
            if str(caller) != str(d.citizen_id) and role not in ("state_admin", "system_admin"):
                return None
        src = await self.db.execute(
            text("""
                SELECT source_type, source_id, source_reference, reason, contribution
                FROM ai.decision_lineage WHERE decision_id = :did ORDER BY created_at, lineage_id
            """),
            {"did": decision_id},
        )
        result = d.result if not isinstance(d.result, str) else json.loads(d.result)
        return {
            "decision_id": str(d.decision_id), "decision_type": d.decision_type,
            "result": result, "confidence_score": d.confidence_score, "abstained": d.abstained,
            "created_at": d.created_at.isoformat(),
            "sources": [dict(s._mapping) for s in src.fetchall()],
        }
