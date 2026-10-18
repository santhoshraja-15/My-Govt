"""Remaining backend services."""
import math
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class GISService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_jurisdiction(self, lat: float, lon: float) -> Optional[dict]:
        try:
            r = await self.db.execute(
                text("SELECT * FROM administration.resolve_jurisdiction(:lon, :lat)"),
                {"lon": lon, "lat": lat},
            )
            row = r.fetchone()
            if not row:
                return None
            return dict(zip(r.keys(), row))
        except Exception:
            # Fallback: nearest district by district_id lookup
            return {
                "ward_id": None, "ward_name": None,
                "local_body_id": None, "local_body_name": None,
                "local_body_type": None, "taluk_id": None, "taluk_name": None,
                "district_id": None, "district_name": None,
                "state_name": "Tamil Nadu", "resolved_level": "unknown",
                "inside_supported_area": False,
            }

    async def get_districts(self) -> list:
        r = await self.db.execute(
            text("""
                SELECT district_id, district_code, district_name, district_name_ta, headquarters
                FROM administration.district ORDER BY district_name
            """)
        )
        cols = list(r.keys())
        return [dict(zip(cols, row)) for row in r.fetchall()]

    async def get_taluks(self, district_id: int) -> list:
        r = await self.db.execute(
            text("SELECT taluk_id, taluk_name, taluk_name_ta FROM administration.taluk WHERE district_id = :did ORDER BY taluk_name"),
            {"did": district_id},
        )
        cols = list(r.keys())
        return [dict(zip(cols, row)) for row in r.fetchall()]

    async def get_nearby_facilities(self, lat: float, lon: float,
                                     radius_km: float, facility_type: Optional[str]) -> list:
        try:
            where = "AND f.facility_type = :ftype" if facility_type else ""
            params: dict = {"lon": lon, "lat": lat, "radius_m": radius_km * 1000}
            if facility_type:
                params["ftype"] = facility_type
            r = await self.db.execute(
                text(f"""
                    SELECT f.facility_id, f.name, f.facility_type,
                           d.department_name, f.address,
                           dist.district_name, f.phone,
                           ST_DistanceSphere(f.location, ST_MakePoint(:lon, :lat)) / 1000 AS distance_km
                    FROM administration.government_facility f
                    LEFT JOIN administration.department d ON d.department_id = f.department_id
                    LEFT JOIN administration.district dist ON dist.district_id = f.district_id
                    WHERE ST_DWithin(
                        f.location::geography,
                        ST_MakePoint(:lon, :lat)::geography,
                        :radius_m
                    ) {where}
                    ORDER BY distance_km ASC
                    LIMIT 20
                """),
                params,
            )
            cols = list(r.keys())
            return [dict(zip(cols, row)) for row in r.fetchall()]
        except Exception:
            return []


class ServiceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_services(self, q, department_id, category, page, page_size) -> dict:
        conditions = ["s.status = 'active'"]
        params: dict = {}
        if q:
            conditions.append("(s.name ILIKE :q OR s.description ILIKE :q)")
            params["q"] = f"%{q}%"
        if department_id:
            conditions.append("s.department_id = :did")
            params["did"] = department_id
        if category:
            conditions.append("s.category = :cat")
            params["cat"] = category
        where = " AND ".join(conditions)
        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM services.service s WHERE {where}"), params
        )
        total = cnt.scalar() or 0
        offset = (page - 1) * page_size
        r = await self.db.execute(
            text(f"""
                SELECT s.service_id, s.service_code, s.name, s.name_ta, s.description,
                       d.department_name, s.category, s.government_fee, s.service_charge,
                       s.processing_days, s.status
                FROM services.service s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                WHERE {where} ORDER BY s.name LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": offset},
        )
        cols = list(r.keys())
        items = [dict(zip(cols, row)) for row in r.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "pages": math.ceil(total / page_size) if total else 0}

    async def get_service(self, service_id: UUID) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT s.service_id, s.service_code, s.name, s.name_ta, s.description,
                       d.department_name, s.category, s.government_fee, s.service_charge,
                       s.processing_days, s.status, s.application_url, s.official_source_url, s.notes
                FROM services.service s
                LEFT JOIN administration.department d ON d.department_id = s.department_id
                WHERE s.service_id = :sid
            """),
            {"sid": str(service_id)},
        )
        row = r.fetchone()
        if not row:
            return None
        data = dict(zip(r.keys(), row))
        # Requirements
        rr = await self.db.execute(
            text("SELECT * FROM services.service_requirement WHERE service_id = :sid"),
            {"sid": str(service_id)},
        )
        data["requirements"] = [dict(zip(rr.keys(), rw)) for rw in rr.fetchall()]
        return data


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_documents(self, q, doc_type, department_id, page, page_size) -> dict:
        conditions = ["d.status = 'active'"]
        params: dict = {}
        if q:
            conditions.append("(d.title ILIKE :q OR d.extracted_text ILIKE :q)")
            params["q"] = f"%{q}%"
        if doc_type:
            conditions.append("d.doc_type = :dt")
            params["dt"] = doc_type
        if department_id:
            conditions.append("d.department_id = :did")
            params["did"] = department_id
        where = " AND ".join(conditions)
        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM documents.document d WHERE {where}"), params
        )
        total = cnt.scalar() or 0
        offset = (page - 1) * page_size
        r = await self.db.execute(
            text(f"""
                SELECT d.document_id, d.title, d.doc_type, dep.department_name,
                       d.language, d.publication_date, d.effective_date,
                       d.status, d.source_url, d.verified_at
                FROM documents.document d
                LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                WHERE {where} ORDER BY d.publication_date DESC NULLS LAST
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": offset},
        )
        cols = list(r.keys())
        items = [dict(zip(cols, row)) for row in r.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "pages": math.ceil(total / page_size) if total else 0}

    async def get_document(self, document_id: UUID) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT d.document_id, d.title, d.doc_type, dep.department_name,
                       d.language, d.publication_date, d.effective_date,
                       d.status, d.source_url, d.verified_at,
                       substring(d.extracted_text, 1, 2000) AS extracted_text,
                       d.summary, d.expiry_date, d.file_hash,
                       (SELECT count(*) FROM documents.document_chunk WHERE document_id = d.document_id) AS chunk_count
                FROM documents.document d
                LEFT JOIN administration.department dep ON dep.department_id = d.department_id
                WHERE d.document_id = :did
            """),
            {"did": str(document_id)},
        )
        row = r.fetchone()
        if not row:
            return None
        return dict(zip(r.keys(), row))

    async def hybrid_search(self, q: str, doc_type: Optional[str], limit: int) -> list:
        where = "AND d.doc_type = :dt" if doc_type else ""
        params: dict = {"q": q, "q_like": f"%{q}%", "lim": limit}
        if doc_type:
            params["dt"] = doc_type
        r = await self.db.execute(
            text(f"""
                SELECT d.document_id, d.title, d.doc_type,
                       substring(d.extracted_text, 1, 300) AS snippet,
                       d.source_url,
                       ts_rank(to_tsvector('simple', coalesce(d.title,'') || ' ' || coalesce(d.extracted_text,'')),
                               websearch_to_tsquery('simple', :q)) AS rank
                FROM documents.document d
                WHERE d.status = 'active' {where}
                  AND (d.title ILIKE :q_like OR d.extracted_text ILIKE :q_like)
                ORDER BY rank DESC, d.publication_date DESC NULLS LAST
                LIMIT :lim
            """),
            params,
        )
        cols = list(r.keys())
        return [dict(zip(cols, row)) for row in r.fetchall()]


class CitizenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, citizen_id) -> Optional[dict]:
        r = await self.db.execute(
            text("""
                SELECT c.citizen_id, c.full_name,
                       cp.date_of_birth, cp.gender, cp.occupation, cp.is_student,
                       cp.annual_income, cp.social_category, cp.disability_status,
                       cp.bpl_status, cp.residence_type, cp.district_id, cp.taluk_id,
                       cp.education_level, cp.marital_status, cp.family_size,
                       cp.held_documents, cp.profile_consent
                FROM identity.citizen c
                LEFT JOIN identity.citizen_profile cp ON cp.citizen_id = c.citizen_id
                WHERE c.citizen_id = :cid
            """),
            {"cid": str(citizen_id)},
        )
        row = r.fetchone()
        if not row:
            return None
        return dict(zip(r.keys(), row))

    async def upsert_profile(self, citizen_id, data) -> dict:
        profile_data = data.model_dump()
        await self.db.execute(
            text("""
                INSERT INTO identity.citizen_profile (citizen_id, date_of_birth, gender, occupation,
                    is_student, annual_income, social_category, disability_status, bpl_status,
                    residence_type, district_id, taluk_id, education_level, marital_status,
                    family_size, held_documents, profile_consent, updated_at)
                VALUES (:cid, :dob, :gender, :occ, :student, :income, :cat, :disability,
                    :bpl, :res, :dist, :taluk, :edu, :marital, :family, :docs, :consent, now())
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
                    profile_consent = EXCLUDED.profile_consent,
                    updated_at = now()
            """),
            {
                "cid": str(citizen_id),
                "dob": profile_data.get("date_of_birth"),
                "gender": profile_data.get("gender"),
                "occ": profile_data.get("occupation"),
                "student": profile_data.get("is_student"),
                "income": profile_data.get("annual_income"),
                "cat": profile_data.get("social_category"),
                "disability": profile_data.get("disability_status"),
                "bpl": profile_data.get("bpl_status"),
                "res": profile_data.get("residence_type"),
                "dist": profile_data.get("district_id"),
                "taluk": profile_data.get("taluk_id"),
                "edu": profile_data.get("education_level"),
                "marital": profile_data.get("marital_status"),
                "family": profile_data.get("family_size"),
                "docs": profile_data.get("held_documents"),
                "consent": profile_data.get("profile_consent", False),
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
                SELECT department_id, department_code, department_name, department_name_ta,
                       short_name, portal_url
                FROM administration.department
                WHERE status = 'active'
                ORDER BY department_name
            """)
        )
        cols = list(r.keys())
        return [dict(zip(cols, row)) for row in r.fetchall()]

    async def get_department(self, department_id: int) -> Optional[dict]:
        r = await self.db.execute(
            text("SELECT * FROM administration.department WHERE department_id = :did"),
            {"did": department_id},
        )
        row = r.fetchone()
        if not row:
            return None
        return dict(zip(r.keys(), row))


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
