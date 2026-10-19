"""Remaining backend services (GIS, e-services, documents, citizen profile, departments).

All SQL targets database/schema/001_schema.sql (+ migrations); the test-suite prepares every
static statement against the real schema (tests/integration/test_sql_schema_conformance.py).
"""
import math
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

PROFILE_CONSENT_PURPOSE = "profile_based_scheme_matching"


class GISService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_jurisdiction(self, lat: float, lon: float) -> Optional[dict]:
        """Resolve a coordinate to ward/local body/taluk/district. Requires PostGIS geometries.

        Returns None when the point lies outside every known boundary (or boundaries are not
        loaded). Database errors propagate - they are not disguised as "outside area".
        """
        r = await self.db.execute(
            text("SELECT ward_id, local_body_id, taluk_id, district_id "
                 "FROM administration.resolve_jurisdiction(:lon, :lat)"),
            {"lon": lon, "lat": lat},
        )
        row = r.fetchone()
        if not row or row.district_id is None:
            return None
        names = await self.db.execute(
            text("""
                SELECT d.district_name, t.name AS taluk_name,
                       lb.name AS local_body_name, lb.type AS local_body_type,
                       w.ward_number AS ward_name
                FROM administration.district d
                LEFT JOIN administration.taluk t ON t.taluk_id = :tid
                LEFT JOIN administration.local_body lb ON lb.local_body_id = :lbid
                LEFT JOIN administration.ward w ON w.ward_id = :wid
                WHERE d.district_id = :did
            """),
            {"did": row.district_id, "tid": row.taluk_id, "lbid": row.local_body_id, "wid": row.ward_id},
        )
        n = names.fetchone()
        level = ("ward" if row.ward_id else "local_body" if row.local_body_id
                 else "taluk" if row.taluk_id else "district")
        return {
            "ward_id": row.ward_id, "ward_name": n.ward_name if n else None,
            "local_body_id": row.local_body_id, "local_body_name": n.local_body_name if n else None,
            "local_body_type": n.local_body_type if n else None,
            "taluk_id": row.taluk_id, "taluk_name": n.taluk_name if n else None,
            "district_id": row.district_id, "district_name": n.district_name if n else None,
            "state_name": "Tamil Nadu", "resolved_level": level, "inside_supported_area": True,
        }

    async def get_districts(self) -> list:
        r = await self.db.execute(
            text("""
                SELECT district_id, district_code, district_name,
                       name_ta AS district_name_ta,
                       headquarters
                FROM administration.district ORDER BY district_name
            """)
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_taluks(self, district_id: int) -> list:
        r = await self.db.execute(
            text("""
                SELECT taluk_id,
                       name  AS taluk_name,
                       name_ta AS taluk_name_ta
                FROM administration.taluk
                WHERE district_id = :did
                ORDER BY name
            """),
            {"did": district_id},
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_nearby_facilities(self, lat: float, lon: float,
                                    radius_km: float, facility_type: Optional[str]) -> list:
        """Nearest government facilities within radius_km. Requires PostGIS."""
        where = "AND f.facility_type = :ftype" if facility_type else ""
        params: dict = {"lon": lon, "lat": lat, "radius_m": radius_km * 1000}
        if facility_type:
            params["ftype"] = facility_type
        r = await self.db.execute(
            text(f"""
                SELECT f.facility_id, f.name, f.facility_type, dist.district_name,
                       f.operator, f.opening_hours,
                       ST_Y(f.location::geometry) AS latitude,
                       ST_X(f.location::geometry) AS longitude,
                       ST_DistanceSphere(f.location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) / 1000
                           AS distance_km
                FROM services.government_facility f
                LEFT JOIN administration.district dist ON dist.district_id = f.district_id
                WHERE ST_DWithin(
                    f.location::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                ) {where}
                ORDER BY distance_km ASC
                LIMIT 20
            """),
            params,
        )
        return [dict(row._mapping) for row in r.fetchall()]


class ServiceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_services(self, q, department_id, category, page, page_size,
                            verification_status: Optional[str] = None) -> dict:
        conditions = ["s.status = 'active'"]
        params: dict = {}
        if q:
            conditions.append("(s.service_name ILIKE :q OR s.description ILIKE :q OR s.name_ta ILIKE :q)")
            params["q"] = f"%{q}%"
        if department_id:
            conditions.append("s.department_id = :did")
            params["did"] = department_id
        if category:
            conditions.append("s.category = :cat")
            params["cat"] = category
        if verification_status:
            conditions.append("s.verification_status = :vstatus")
            params["vstatus"] = verification_status
        where = " AND ".join(conditions)
        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM services.service s WHERE {where}"), params
        )
        total = cnt.scalar() or 0
        r = await self.db.execute(
            text(f"""
                SELECT s.service_id, s.service_code, s.service_name AS name, s.name_ta, s.description,
                       d.department_name, s.category, s.government_fee::float AS government_fee,
                       s.service_charge::float AS service_charge,
                       s.processing_time, s.status,
                       s.verification_status, s.source_document_ref,
                       (s.verification_status = 'official_verified') AS charges_verified
                FROM services.service s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                WHERE {where} ORDER BY s.service_name LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": (page - 1) * page_size},
        )
        items = [dict(row._mapping) for row in r.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "pages": math.ceil(total / page_size) if total else 0}

    async def get_categories(self) -> list:
        r = await self.db.execute(text(
            "SELECT DISTINCT category FROM services.service WHERE category IS NOT NULL AND status = 'active' ORDER BY category"))
        return [row[0] for row in r.fetchall()]

    async def get_service(self, service_id: UUID) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT s.service_id, s.service_code, s.service_name AS name, s.name_ta, s.description,
                       d.department_name, s.category, s.government_fee::float AS government_fee,
                       s.service_charge::float AS service_charge,
                       s.processing_time, s.status,
                       s.verification_status, s.source_document_ref,
                       (s.verification_status = 'official_verified') AS charges_verified,
                       s.application_url, s.official_url AS official_source_url,
                       s.statutory_act_ref AS notes
                FROM services.service s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                WHERE s.service_id = :sid
            """),
            {"sid": service_id},
        )
        row = r.fetchone()
        if not row:
            return None
        data = dict(row._mapping)
        rr = await self.db.execute(
            text("""
                SELECT requirement_id, document_name AS document_type, description, mandatory
                FROM services.service_requirement WHERE service_id = :sid
            """),
            {"sid": service_id},
        )
        data["requirements"] = [dict(rw._mapping) for rw in rr.fetchall()]
        return data


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_documents(self, q, doc_type, department_id, page, page_size) -> dict:
        conditions = ["d.status = 'active'"]
        params: dict = {}
        if q:
            conditions.append("(d.title ILIKE :q OR d.full_text ILIKE :q)")
            params["q"] = f"%{q}%"
        if doc_type:
            conditions.append("d.document_type = :dt")
            params["dt"] = doc_type
        if department_id:
            conditions.append("d.department_id = :did")
            params["did"] = department_id
        where = " AND ".join(conditions)
        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM documents.document d WHERE {where}"), params
        )
        total = cnt.scalar() or 0
        r = await self.db.execute(
            text(f"""
                SELECT d.document_id, d.title, d.document_type AS doc_type, dep.department_name,
                       coalesce(d.language, 'en') AS language, d.publication_date, d.effective_date,
                       d.status, d.source_url, NULL::text AS verified_at
                FROM documents.document d
                LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                WHERE {where} ORDER BY d.publication_date DESC NULLS LAST
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": (page - 1) * page_size},
        )
        items = [dict(row._mapping) for row in r.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "pages": math.ceil(total / page_size) if total else 0}

    async def get_document(self, document_id: UUID) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT d.document_id, d.title, d.document_type AS doc_type, dep.department_name,
                       coalesce(d.language, 'en') AS language, d.publication_date, d.effective_date,
                       d.status, d.source_url, NULL::text AS verified_at,
                       substring(d.full_text, 1, 2000) AS extracted_text,
                       NULL::text AS summary, d.expiry_date, d.file_hash,
                       (SELECT count(*) FROM documents.document_chunk
                        WHERE document_id = d.document_id)::int AS chunk_count
                FROM documents.document d
                LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                WHERE d.document_id = :did
            """),
            {"did": document_id},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def hybrid_search(self, q: str, doc_type: Optional[str], limit: int) -> list:
        where = "AND d.document_type = :dt" if doc_type else ""
        params: dict = {"q": q, "q_like": f"%{q}%", "lim": limit}
        if doc_type:
            params["dt"] = doc_type
        r = await self.db.execute(
            text(f"""
                SELECT d.document_id, d.title, d.document_type AS doc_type,
                       substring(d.full_text, 1, 300) AS snippet,
                       d.source_url,
                       ts_rank(to_tsvector('simple', coalesce(d.title,'') || ' ' || coalesce(d.full_text,'')),
                               websearch_to_tsquery('simple', :q)) AS rank
                FROM documents.document d
                WHERE d.status = 'active' {where}
                  AND (d.title ILIKE :q_like OR d.full_text ILIKE :q_like)
                ORDER BY rank DESC, d.publication_date DESC NULLS LAST
                LIMIT :lim
            """),
            params,
        )
        return [dict(row._mapping) for row in r.fetchall()]


class CitizenService:
    """Citizen profile. Consent lives in identity.consent (purpose = profile_based_scheme_matching)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, citizen_id) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT c.citizen_id, c.name AS full_name,
                       cp.date_of_birth, cp.gender, cp.occupation, cp.is_student,
                       cp.annual_income::float AS annual_income, cp.social_category,
                       cp.disability_status, cp.bpl_status, cp.residence_type,
                       cp.district_id, cp.taluk_id,
                       cp.education_level, cp.marital_status, cp.family_size,
                       cp.held_documents,
                       coalesce((SELECT granted FROM identity.consent
                                 WHERE citizen_id = c.citizen_id AND purpose = :purpose
                                 ORDER BY granted_at DESC, consent_id LIMIT 1), false) AS profile_consent
                FROM identity.citizen c
                LEFT JOIN identity.citizen_profile cp ON cp.citizen_id = c.citizen_id
                WHERE c.citizen_id = :cid
            """),
            {"cid": citizen_id, "purpose": PROFILE_CONSENT_PURPOSE},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def upsert_profile(self, citizen_id, data) -> Optional[dict]:
        """Store the profile only while consent is granted; revoking consent clears the profile."""
        p = data.model_dump()
        current = await self.get_profile(citizen_id)
        if current is None:
            raise LookupError("Citizen not found")
        if bool(current["profile_consent"]) != bool(p["profile_consent"]):
            await self.db.execute(
                text("INSERT INTO identity.consent (citizen_id, purpose, granted) VALUES (:cid, :purpose, :g)"),
                {"cid": citizen_id, "purpose": PROFILE_CONSENT_PURPOSE, "g": bool(p["profile_consent"])},
            )
        if not p["profile_consent"]:
            await self.db.execute(
                text("DELETE FROM identity.citizen_profile WHERE citizen_id = :cid"), {"cid": citizen_id}
            )
            await self.db.commit()
            return await self.get_profile(citizen_id)
        await self.db.execute(
            text("""
                INSERT INTO identity.citizen_profile (citizen_id, date_of_birth, gender, occupation,
                    is_student, annual_income, social_category, disability_status, bpl_status,
                    residence_type, district_id, taluk_id, education_level, marital_status,
                    family_size, held_documents, updated_at)
                VALUES (:cid, :dob, :gender, :occ, :student, :income, :cat, :disability,
                    :bpl, :res, :dist, :taluk, :edu, :marital, :family, :docs, now())
                ON CONFLICT (citizen_id) DO UPDATE SET
                    date_of_birth = EXCLUDED.date_of_birth,
                    gender = EXCLUDED.gender,
                    occupation = EXCLUDED.occupation,
                    is_student = EXCLUDED.is_student,
                    annual_income = EXCLUDED.annual_income,
                    social_category = EXCLUDED.social_category,
                    disability_status = EXCLUDED.disability_status,
                    bpl_status = EXCLUDED.bpl_status,
                    residence_type = EXCLUDED.residence_type,
                    district_id = EXCLUDED.district_id,
                    taluk_id = EXCLUDED.taluk_id,
                    education_level = EXCLUDED.education_level,
                    marital_status = EXCLUDED.marital_status,
                    family_size = EXCLUDED.family_size,
                    held_documents = EXCLUDED.held_documents,
                    updated_at = now()
            """),
            {
                "cid": citizen_id, "dob": p["date_of_birth"], "gender": p["gender"],
                "occ": p["occupation"], "student": p["is_student"], "income": p["annual_income"],
                "cat": p["social_category"], "disability": p["disability_status"],
                "bpl": p["bpl_status"], "res": p["residence_type"], "dist": p["district_id"],
                "taluk": p["taluk_id"], "edu": p["education_level"], "marital": p["marital_status"],
                "family": p["family_size"], "docs": p["held_documents"] or [],
            },
        )
        await self.db.commit()
        return await self.get_profile(citizen_id)


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_departments(self) -> list:
        r = await self.db.execute(
            text("""
                SELECT department_id, department_code, department_name,
                       name_ta AS department_name_ta, short_name,
                       website_url AS portal_url,
                       verification_status, source_document_ref
                FROM administration.department
                WHERE status = 'active'
                ORDER BY department_name
            """)
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_department(self, department_id: int) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT department_id, department_code, department_name, name_ta,
                       name_ta AS department_name_ta, short_name, description,
                       website_url, website_url AS portal_url, contact_email, contact_phone,
                       status, verification_status, source_document_ref
                FROM administration.department WHERE department_id = :did
            """),
            {"did": department_id},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None


class GraphService:
    async def get_stats(self) -> dict:
        from app.core.config import settings
        if not settings.FEATURE_GRAPH:
            return {"status": "disabled"}
        try:
            from neo4j import AsyncGraphDatabase
            driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            async with driver.session() as session:
                r = await session.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt"
                )
                nodes = {rec["label"]: rec["cnt"] async for rec in r}
                r2 = await session.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS cnt")
                rels = {rec["t"]: rec["cnt"] async for rec in r2}
            await driver.close()
            return {"status": "healthy", "node_counts": nodes, "relationship_counts": rels}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}
