"""Pure logic of the architecture explorer: cardinality, junction tables, inferred links, normalization notes."""
from app.services import architecture_service as arch


def table(key, cols, pk, fks=(), unique=(), indexes=()):
    schema, name = key.split(".")
    t = {"key": key, "schema": schema, "name": name, "comment": None, "partitioned": False, "domain": "d", "color": "#000", "primary_key": list(pk),
         "unique": [{"name": f"u_{i}", "columns": list(u)} for i, u in enumerate(unique)], "checks": [], "foreign_keys": [], "indexes": list(indexes),
         "referenced_by": [], "row_count": 0,
         "columns": [{"name": c, "type": "int4", "not_null": nn, "default": None} for c, nn in cols]}
    for i, (fcols, target, tcols) in enumerate(fks):
        t["foreign_keys"].append({"name": f"fk_{name}_{i}", "from_table": key, "from_columns": list(fcols), "to_table": target,
                                  "to_columns": list(tcols), "on_delete": "NO ACTION", "on_update": "NO ACTION", "enforced": True, "kind": "foreign_key"})
    return t


def catalog(*tables):
    cat = {"schemas": sorted({t["schema"] for t in tables}), "tables": {t["key"]: t for t in tables}, "foreign_keys": []}
    for t in tables:
        cat["foreign_keys"] += t["foreign_keys"]
    for fk in cat["foreign_keys"]:
        cat["tables"][fk["to_table"]]["referenced_by"].append({"table": fk["from_table"], "columns": fk["from_columns"], "constraint": fk["name"]})
        arch._annotate_cardinality(cat["tables"], fk)
    return cat


def test_cardinality_follows_uniqueness_and_nullability():
    parent = table("a.parent", [("id", True)], ["id"])
    many = table("a.many", [("id", True), ("parent_id", True)], ["id"], fks=[(["parent_id"], "a.parent", ["id"])])
    opt = table("a.opt", [("id", True), ("parent_id", False)], ["id"], fks=[(["parent_id"], "a.parent", ["id"])])
    one = table("a.one", [("id", True), ("parent_id", True)], ["id"], fks=[(["parent_id"], "a.parent", ["id"])], unique=[["parent_id"]])
    shared_pk = table("a.shared", [("parent_id", True)], ["parent_id"], fks=[(["parent_id"], "a.parent", ["id"])])
    cat = catalog(parent, many, opt, one, shared_pk)
    got = {t["key"]: (t["foreign_keys"][0]["cardinality"], t["foreign_keys"][0]["notation"]) for t in cat["tables"].values() if t["foreign_keys"]}
    assert got == {"a.many": ("one_to_many", "1 : 1..N"), "a.opt": ("one_to_many", "1 : 0..N"),
                   "a.one": ("one_to_one", "1 : 1"), "a.shared": ("one_to_one", "1 : 1")}


def test_unique_index_counts_as_uniqueness_but_expression_index_does_not():
    parent = table("a.parent", [("id", True)], ["id"])
    idx = {"name": "i", "method": "btree", "unique": True, "primary": False, "definition": "CREATE UNIQUE INDEX i ON a.child USING btree (parent_id)"}
    expr = {"name": "j", "method": "btree", "unique": True, "primary": False, "definition": "CREATE UNIQUE INDEX j ON a.child USING btree (lower((x)::text))"}
    child = table("a.child", [("id", True), ("parent_id", True)], ["id"], fks=[(["parent_id"], "a.parent", ["id"])], indexes=[idx, expr])
    assert catalog(parent, child)["foreign_keys"][0]["cardinality"] == "one_to_one"
    assert arch._index_columns(expr["definition"]) is None


def test_junction_table_is_many_to_many_only_when_the_key_is_made_of_foreign_keys():
    a, b = table("s.a", [("id", True)], ["id"]), table("s.b", [("id", True)], ["id"])
    link = table("s.a_b", [("a_id", True), ("b_id", True)], ["a_id", "b_id"], fks=[(["a_id"], "s.a", ["id"]), (["b_id"], "s.b", ["id"])])
    assert [(r["from_table"], r["to_table"], r["cardinality"]) for r in arch.junction_relationships(catalog(a, b, link))] == [("s.a", "s.b", "many_to_many")]
    surrogate = table("s.a_b2", [("id", True), ("a_id", True), ("b_id", True)], ["id"], fks=[(["a_id"], "s.a", ["id"]), (["b_id"], "s.b", ["id"])])
    assert arch.junction_relationships(catalog(a, b, surrogate)) == []


def test_inferred_relationships_are_labelled_unenforced_and_skip_real_foreign_keys():
    dept = table("x.department", [("department_id", True)], ["department_id"])
    enforced = table("x.thing", [("id", True), ("department_id", True)], ["id"], fks=[(["department_id"], "x.department", ["department_id"])])
    loose = table("x.note", [("id", True), ("department_id", False)], ["id"])
    out = arch.inferred_relationships(catalog(dept, enforced, loose))
    assert [(r["from_table"], r["to_table"], r["enforced"]) for r in out] == [("x.note", "x.department", False)]
    assert "not enforced" in out[0]["notation"]


def test_normalization_reports_facts_and_never_asserts_third_normal_form():
    t = table("n.t", [("id", True), ("tags", False)], ["id"])
    t["columns"][1]["type"] = "jsonb"
    key = table("n.k", [("a", True), ("b", True)], ["a", "b"])
    nokey = table("n.nokey", [("x", False)], [])
    rows = {r["table"]: r for r in arch.normalization(catalog(t, key, nokey))["tables"]}
    assert rows["n.t"]["non_atomic_candidates"] == ["tags"] and "holds" in rows["n.t"]["second_nf"]
    assert rows["n.k"]["composite_candidate_keys"] == [["a", "b"]] and "needs functional-dependency" in rows["n.k"]["second_nf"]
    assert rows["n.nokey"]["has_primary_key"] is False and "no primary key" in rows["n.nokey"]["first_nf"]
    assert all("cannot be established" in r["third_nf"] for r in rows.values())


def test_redundancy_hint_is_a_recommendation_for_non_generic_duplicate_columns():
    dept = table("r.department", [("department_id", True), ("department_name", True), ("status", True)], ["department_id"])
    emp = table("r.employee", [("id", True), ("department_id", True), ("department_name", False), ("status", True)], ["id"],
                fks=[(["department_id"], "r.department", ["department_id"])])
    hints = arch.normalization(catalog(dept, emp))["tables"]
    emp_hint = next(r for r in hints if r["table"] == "r.employee")["possible_redundancy"]
    assert [h["column"] for h in emp_hint] == ["department_name"]            # 'status' is generic and ignored


def test_relational_notation_marks_keys_and_example_joins_use_real_columns():
    parent = table("a.parent", [("id", True)], ["id"])
    child = table("a.child", [("id", True), ("parent_id", True), ("note", False)], ["id"], fks=[(["parent_id"], "a.parent", ["id"])])
    cat = catalog(parent, child)
    n = arch.relational_notation(cat["tables"]["a.child"])
    assert n["notation"] == "CHILD(PK:id, FK:parent_id, note)" and n["not_null"] == ["parent_id"]
    joins = arch.example_joins(cat, "a.child") + arch.example_joins(cat, "a.parent")
    assert any('a."parent_id" = b."id"' in j["sql"] for j in joins) and any(j["direction"] == "referenced by" for j in joins)


def test_identifier_quoting_blocks_injection_in_generated_sql():
    assert arch.q('x"; DROP TABLE y; --') == '"x""; DROP TABLE y; --"'


def test_postgres_display_name_is_short_on_every_platform():
    linux = "PostgreSQL 16.4 (Debian 16.4-1.pgdg120+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14) 12.2.0, 64-bit"
    windows = "PostgreSQL 16.15, compiled by Visual C++ build 1944, 64-bit"
    assert arch.pg_display_name(linux) == "PostgreSQL 16.4"
    assert arch.pg_display_name(windows) == "PostgreSQL 16.15"
    assert arch.pg_display_name("") == arch.pg_display_name(None) == arch.pg_display_name("something else") == "PostgreSQL"
