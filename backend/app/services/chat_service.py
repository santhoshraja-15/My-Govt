"""AI Chat service — hybrid retrieval, trust engine, LLM orchestration."""
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


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_message(self, request: ChatRequest, current_user) -> ChatResponse:
        message_id = uuid.uuid4()
        conversation_id = request.conversation_id or uuid.uuid4()

        # Persist conversation if authenticated
        if current_user:
            await self._ensure_conversation(conversation_id, current_user.user_id)

        # Classify intent & detect language
        intent = _classify_intent(request.message)
        language = request.language or _detect_language(request.message)

        # Hybrid retrieval
        retrieved = await self._hybrid_retrieve(request.message, intent, limit=8)

        # Build context
        context_text, citations = self._build_context(retrieved)

        # Trust score
        trust_score = self._compute_trust(retrieved)

        # Try LLM, fall back to deterministic template
        answer, abstained, abstain_reason, degraded = await self._generate_answer(
            request.message, intent, context_text, language, trust_score
        )

        # Suggested actions
        actions = self._suggest_actions(intent)

        # Persist messages
        decision_id = uuid.uuid4()
        if current_user:
            await self._save_messages(
                conversation_id, message_id, request.message, answer,
                citations, trust_score, intent, decision_id
            )

        # Persist decision lineage
        await self._save_decision(decision_id, {
            "query": request.message,
            "intent": intent,
            "language": language,
            "retrieved_count": len(retrieved),
            "trust_score": trust_score,
            "degraded": degraded,
        })

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
        )

    async def _hybrid_retrieve(self, query: str, intent: str, limit: int = 8) -> list[dict]:
        """Hybrid: full-text + keyword search (vector search when embeddings ready)."""
        results: list[dict] = []

        # Scheme search
        if intent in ("scheme_search", "eligibility_check", "general_query"):
            r = await self.db.execute(
                text("""
                    SELECT s.scheme_id::text, s.name AS title, s.description,
                           d.department_name, 'scheme' AS entity_type,
                           s.verified_at, sr.url AS source_url, sr.reliability_score
                    FROM schemes.scheme s
                    LEFT JOIN administration.department d ON d.department_id = s.department_id
                    LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
                    WHERE s.status = 'active'
                      AND (s.name ILIKE :q OR s.description ILIKE :q)
                    ORDER BY length(s.name) ASC
                    LIMIT :lim
                """),
                {"q": f"%{query}%", "lim": limit},
            )
            cols = list(r.keys())
            results.extend([dict(zip(cols, row)) for row in r.fetchall()])

        # Document / policy search
        if intent in ("policy_query", "general_query"):
            r = await self.db.execute(
                text("""
                    SELECT d.document_id::text, d.title,
                           substring(d.extracted_text, 1, 500) AS description,
                           dep.department_name, 'document' AS entity_type,
                           d.verified_at::text AS verified_at, d.source_url,
                           1.0 AS reliability_score
                    FROM documents.document d
                    LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                    WHERE d.status = 'active'
                      AND (d.title ILIKE :q OR d.extracted_text ILIKE :q)
                    LIMIT :lim
                """),
                {"q": f"%{query}%", "lim": limit // 2},
            )
            cols = list(r.keys())
            results.extend([dict(zip(cols, row)) for row in r.fetchall()])

        return results[:limit]

    def _build_context(self, retrieved: list[dict]) -> tuple[str, list[Citation]]:
        citations: list[Citation] = []
        context_parts: list[str] = []

        for i, item in enumerate(retrieved, 1):
            title = item.get("title", "")
            description = item.get("description") or ""
            dept = item.get("department_name", "")
            source_url = item.get("source_url")
            verified_at = item.get("verified_at")

            context_parts.append(
                f"[{i}] **{title}** ({dept})\n{description[:400]}"
            )
            citations.append(Citation(
                index=i,
                title=title,
                department=dept,
                source_url=source_url,
                verified_at=str(verified_at) if verified_at else None,
            ))

        return "\n\n".join(context_parts), citations

    def _compute_trust(self, retrieved: list[dict]) -> float:
        if not retrieved:
            return 0.0
        scores = [float(r.get("reliability_score") or 0.5) for r in retrieved]
        return round(sum(scores) / len(scores), 3)

    async def _generate_answer(
        self, query: str, intent: str, context: str,
        language: str, trust_score: float
    ) -> tuple[str, bool, Optional[str], bool]:
        """Generate answer — LLM or deterministic fallback."""

        # Abstain if trust too low and no context
        if trust_score < settings.TRUST_THRESHOLD and not context:
            msg = (
                "I couldn't find verified information to answer your question reliably. "
                "Please visit the official Tamil Nadu government portal at https://www.tn.gov.in "
                "or contact your nearest e-Sevai centre."
            )
            return msg, True, "trust_threshold_not_met", False

        # Try configured LLM provider
        if settings.LLM_PROVIDER != "none" and settings.LLM_API_KEY:
            try:
                answer = await self._call_llm(query, context, language)
                return answer, False, None, False
            except Exception as e:
                logger.warning("LLM call failed, using template", error=str(e))

        # Deterministic template fallback
        answer = self._template_answer(query, intent, context, language)
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

    def _template_answer(self, query: str, intent: str, context: str, language: str) -> str:
        if not context:
            if language == "ta":
                return "மன்னிக்கவும், இந்தக் கேள்விக்கான சரிபார்க்கப்பட்ட தகவல் கிடைக்கவில்லை."
            return ("I found limited verified information for your query. "
                    "Please check https://www.tn.gov.in or your nearest e-Sevai centre.")

        lines = [
            "Based on verified government information, here is what I found:\n",
            context[:1500],
            "\n\n*This information is sourced from official government records. "
            "For official confirmation, please visit the respective department portal.*",
        ]
        return "\n".join(lines)

    def _suggest_actions(self, intent: str) -> list[str]:
        mapping = {
            "scheme_search": ["Browse all schemes", "Check eligibility", "Contact department"],
            "service_lookup": ["Apply online", "Find nearest e-Sevai", "Download forms"],
            "complaint_status": ["Track complaint", "File new complaint"],
            "policy_query": ["Download document", "Contact department"],
            "eligibility_check": ["Check eligibility", "Update profile"],
        }
        return mapping.get(intent, ["Browse services", "Contact us"])

    async def _ensure_conversation(self, conversation_id: UUID, user_id) -> None:
        try:
            r = await self.db.execute(
                text("SELECT conversation_id FROM ai.conversation WHERE conversation_id = :cid"),
                {"cid": str(conversation_id)},
            )
            if not r.fetchone():
                await self.db.execute(
                    text("""
                        INSERT INTO ai.conversation (conversation_id, user_id, created_at, updated_at)
                        VALUES (:cid, :uid, now(), now())
                        ON CONFLICT DO NOTHING
                    """),
                    {"cid": str(conversation_id), "uid": str(user_id)},
                )
                await self.db.commit()
        except Exception as e:
            logger.warning("Could not persist conversation", error=str(e))

    async def _save_messages(self, conv_id, msg_id, user_msg, answer,
                              citations, trust_score, intent, decision_id) -> None:
        try:
            import json
            # User message
            await self.db.execute(
                text("""
                    INSERT INTO ai.message (message_id, conversation_id, role, content, created_at)
                    VALUES (:mid, :cid, 'user', :content, now())
                """),
                {"mid": str(uuid.uuid4()), "cid": str(conv_id), "content": user_msg},
            )
            # Assistant message
            await self.db.execute(
                text("""
                    INSERT INTO ai.message (message_id, conversation_id, role, content,
                                           trust_score, intent, decision_id, created_at)
                    VALUES (:mid, :cid, 'assistant', :content, :ts, :intent, :did, now())
                """),
                {
                    "mid": str(msg_id), "cid": str(conv_id),
                    "content": answer, "ts": trust_score,
                    "intent": intent, "did": str(decision_id),
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.warning("Could not persist messages", error=str(e))

    async def _save_decision(self, decision_id: UUID, lineage: dict) -> None:
        try:
            import json
            await self.db.execute(
                text("""
                    INSERT INTO ai.decision_lineage (decision_id, lineage_json, created_at)
                    VALUES (:did, :lineage, now())
                """),
                {"did": str(decision_id), "lineage": json.dumps(lineage)},
            )
            await self.db.commit()
        except Exception as e:
            logger.warning("Could not persist decision lineage", error=str(e))

    async def get_conversations(self, user_id) -> list:
        try:
            r = await self.db.execute(
                text("""
                    SELECT c.conversation_id, c.created_at, c.updated_at AS last_message_at,
                           count(m.message_id) AS message_count,
                           (SELECT content FROM ai.message WHERE conversation_id = c.conversation_id
                            AND role = 'user' ORDER BY created_at DESC LIMIT 1) AS preview
                    FROM ai.conversation c
                    LEFT JOIN ai.message m ON m.conversation_id = c.conversation_id
                    WHERE c.user_id = :uid
                    GROUP BY c.conversation_id, c.created_at, c.updated_at
                    ORDER BY c.updated_at DESC
                    LIMIT 50
                """),
                {"uid": str(user_id)},
            )
            cols = list(r.keys())
            return [dict(zip(cols, row)) for row in r.fetchall()]
        except Exception:
            return []

    async def get_messages(self, conversation_id: UUID, current_user) -> Optional[list]:
        try:
            r = await self.db.execute(
                text("""
                    SELECT message_id, role, content, created_at
                    FROM ai.message
                    WHERE conversation_id = :cid
                    ORDER BY created_at ASC
                """),
                {"cid": str(conversation_id)},
            )
            cols = list(r.keys())
            return [dict(zip(cols, row)) for row in r.fetchall()]
        except Exception:
            return []

    async def get_decision_lineage(self, decision_id: UUID) -> Optional[dict]:
        try:
            import json
            r = await self.db.execute(
                text("SELECT lineage_json FROM ai.decision_lineage WHERE decision_id = :did"),
                {"did": str(decision_id)},
            )
            row = r.fetchone()
            if not row:
                return None
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            return None
