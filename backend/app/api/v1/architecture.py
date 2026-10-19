"""Database Architecture Explorer API: read-only metadata about the REAL database and backend.

Restricted to state/system administrators: the metadata describes internal structure. No secrets, connection strings or
environment variables are returned, and row data appears only as small samples of public catalogue tables.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.security.dependencies import require_role
from app.services import architecture_service as arch
from app.services import audit

router = APIRouter()
admin_dep = require_role(["system_admin", "state_admin"])


async def _catalog(db: AsyncSession, counts: bool = False) -> dict:
    catalog = await arch.load_catalog(db)
    if counts:
        await arch.add_row_counts(db, catalog)
    return catalog


def _column(t: dict, c: dict) -> dict:
    ref = next(({"table": fk["to_table"], "column": fk["to_columns"][i]} for fk in t["foreign_keys"]
                for i, fc in enumerate(fk["from_columns"]) if fc == c["name"]), None)
    return {**c, "pk": c["name"] in t["primary_key"], "fk": ref is not None, "references": ref,
            "unique": any(c["name"] in u["columns"] and len(u["columns"]) == 1 for u in t["unique"])}


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    catalog = await _catalog(db, counts=True)
    comps = await arch.components(db, catalog)
    tables = list(catalog["tables"].values())
    junction = arch.junction_relationships(catalog)
    inferred = arch.inferred_relationships(catalog)
    version = comps["nodes"][3]["name"]
    engines = [{"name": n["name"], "role": n["role"], "status": n["status"]} for n in comps["nodes"] if n["layer"] == "data"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": version,
        "counts": {
            "schemas": len(catalog["schemas"]), "tables": len(tables), "columns": sum(len(t["columns"]) for t in tables),
            "foreign_keys": len(catalog["foreign_keys"]), "junction_relationships": len(junction), "inferred_relationships": len(inferred),
            "indexes": sum(len(t["indexes"]) for t in tables), "rows": sum(t["row_count"] or 0 for t in tables),
            "data_technologies": len(engines),
        },
        "schemas": [{"name": s, "domain": arch.DOMAINS.get(s, (s, ""))[0], "color": arch.DOMAINS.get(s, ("", "#64748b"))[1],
                     "tables": sum(1 for t in tables if t["schema"] == s)} for s in catalog["schemas"]],
        "technologies": engines,
        "demo_data_included": comps["demo_data_included"],
    }


@router.get("/components")
async def components(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    return await arch.components(db, await _catalog(db))


@router.get("/tables")
async def tables(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    catalog = await _catalog(db, counts=True)
    return {"items": [arch.table_summary(t) for t in catalog["tables"].values()], "total": len(catalog["tables"])}


@router.get("/tables/{schema}/{table}")
async def table_detail(schema: str, table: str, request: Request, db: AsyncSession = Depends(get_db), user=Depends(admin_dep)):
    catalog = await _catalog(db, counts=True)
    key = f"{schema}.{table}"
    t = catalog["tables"].get(key)
    if t is None:
        raise HTTPException(status_code=404, detail="Unknown table")
    usage = arch.source_usage(sorted(catalog["tables"]))
    sample = await arch.sample_rows(db, t)
    await audit.record(db, action="ARCHITECTURE_TABLE_VIEWED", entity_type="table", entity_id=key, user=user, request=request,
                       new={"sample_shown": sample.get("available", False)})
    return {
        **arch.table_summary(t),
        "columns": [_column(t, c) for c in t["columns"]],
        "unique_constraints": t["unique"], "check_constraints": t["checks"], "indexes": t["indexes"],
        "references": [{"table": fk["to_table"], "constraint": fk["name"], "columns": fk["from_columns"], "to_columns": fk["to_columns"],
                        "cardinality": fk["cardinality"], "notation": fk["notation"], "participation": fk["child_participation"],
                        "on_delete": fk["on_delete"]} for fk in t["foreign_keys"]],
        "referenced_by": [{**r, "cardinality": next(f for f in catalog["tables"][r["table"]]["foreign_keys"] if f["name"] == r["constraint"])["cardinality"]}
                          for r in t["referenced_by"]],
        "used_in": usage.get(key, []), "example_joins": arch.example_joins(catalog, key), "sample": sample,
    }


@router.get("/relationships")
async def relationships(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    catalog = await _catalog(db)
    junction = arch.junction_relationships(catalog)
    inferred = arch.inferred_relationships(catalog)
    return {"foreign_keys": catalog["foreign_keys"], "many_to_many": junction, "inferred": inferred,
            "summary": {"foreign_keys": len(catalog["foreign_keys"]), "many_to_many": len(junction), "inferred": len(inferred),
                        "one_to_one": sum(1 for f in catalog["foreign_keys"] if f["cardinality"] == "one_to_one"),
                        "one_to_many": sum(1 for f in catalog["foreign_keys"] if f["cardinality"] == "one_to_many")},
            "legend": {"foreign_key": "enforced by a FOREIGN KEY constraint", "junction": "many-to-many through a junction table (its primary key is made of foreign keys)",
                       "inferred": "looks like a reference by column name, but the database does not enforce it"}}


@router.get("/schema")
async def relational_schema(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    catalog = await _catalog(db)
    return {"relations": [arch.relational_notation(t) for t in catalog["tables"].values()], "total": len(catalog["tables"])}


@router.get("/normalization")
async def normalization(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    return arch.normalization(await _catalog(db))


@router.get("/advanced")
async def advanced(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    return await arch.advanced(db, await _catalog(db, counts=True))


@router.get("/implementation")
async def implementation(db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    catalog = await _catalog(db)
    comps = await arch.components(db, catalog)
    return {"engine": comps["nodes"][3]["name"], "extensions": comps["nodes"][3].get("extensions", {}), "files": arch.database_files(),
            "examples": [{k: v for k, v in e.items()} for e in arch.EXAMPLES]}


@router.get("/examples/{example_id}/run")
async def run_example(example_id: str, request: Request, db: AsyncSession = Depends(get_db), user=Depends(admin_dep)):
    example = arch.example_by_id(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="Unknown example")
    result = await arch.run_example(db, example)
    await audit.record(db, action="ARCHITECTURE_EXAMPLE_RUN", entity_type="example_query", entity_id=example_id, user=user, request=request,
                       new={"rows": result["row_count"]})
    return {"id": example_id, **result}


@router.get("/examples/{example_id}/explain")
async def explain_example(example_id: str, db: AsyncSession = Depends(get_db), _=Depends(admin_dep)):
    example = arch.example_by_id(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="Unknown example")
    return {"id": example_id, **await arch.explain_example(db, example)}
