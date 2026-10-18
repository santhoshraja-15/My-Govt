"""Admin API endpoints — database intelligence, datasets, health."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.health import get_health_status
from app.services.admin_service import AdminService
from app.security.dependencies import require_role
from app.services import audit

router = APIRouter()
admin_dep = require_role(["system_admin", "state_admin", "data_steward"])


# ── Health & Overview ─────────────────────────────────────────
@router.get("/health")
async def admin_health():
    return await get_health_status()


@router.get("/overview")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_overview()


# ── Database connections ──────────────────────────────────────
@router.get("/databases/connections")
async def db_connections(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_connection_status()


# ── Schema explorer ───────────────────────────────────────────
@router.get("/schemas")
async def list_schemas(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.list_schemas()


@router.get("/schemas/{schema_name}/tables")
async def list_tables(
    schema_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.list_tables(schema_name)


@router.get("/schemas/{schema_name}/tables/{table_name}")
async def get_table_detail(
    schema_name: str,
    table_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_table_detail(schema_name, table_name)


@router.get("/schemas/{schema_name}/tables/{table_name}/sample")
async def get_table_sample(
    request: Request,
    schema_name: str,
    table_name: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin=Depends(admin_dep),
):
    svc = AdminService(db)
    await audit.record(db, action="ADMIN_TABLE_SAMPLE", entity_type="table", entity_id=f"{schema_name}.{table_name}",
                       user=admin, request=request)
    return await svc.get_table_sample(schema_name, table_name, limit=limit, offset=offset)


# ── Relationships ─────────────────────────────────────────────
@router.get("/relationships")
async def get_relationships(
    schema_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_relationships(schema_name)


# ── Safe SQL workspace ────────────────────────────────────────
@router.post("/query")
async def run_query(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_role(["system_admin"])),
):
    svc = AdminService(db)
    sql = str(payload.get("sql", "")).strip()
    result = await svc.run_safe_query(sql)
    await audit.record(db, action="ADMIN_SQL_QUERY", entity_type="sql_workspace", user=admin, request=request,
                       new={"query_prefix": sql[:200], "rejected": "error" in result},
                       outcome="failure" if "error" in result else "success")
    return result


# ── Dataset registry ──────────────────────────────────────────
@router.get("/datasets")
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.list_datasets()


@router.get("/sources")
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.list_sources()


# ── Audit logs ────────────────────────────────────────────────
@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_audit_logs(limit=limit, offset=offset)


# ── Knowledge graph stats ─────────────────────────────────────
@router.get("/knowledge-graph/stats")
async def kg_stats(_=Depends(admin_dep)):
    from app.services.graph_service import GraphService
    svc = GraphService()
    return await svc.get_stats()


# ── Data quality ─────────────────────────────────────────────
@router.get("/data-quality")
async def data_quality(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_dep),
):
    svc = AdminService(db)
    return await svc.get_data_quality_report()
