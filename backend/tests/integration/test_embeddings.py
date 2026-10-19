"""Embedding generation: providers, validation, retries, partial failure, re-embedding, idempotence."""
import uuid

import httpx
import pytest

from app.ai.embeddings import run as emb
from app.ai.embeddings.providers import (
    DeterministicTestProvider, DimensionMismatch, EmbeddingError, OpenAIProvider, check_dimensions, get_provider,
)
from app.core.config import settings

DIM = settings.EMBEDDING_DIMENSION


# -- providers (no DB) ----------------------------------------------------------------------------
async def test_deterministic_provider_is_stable_normalised_and_dimension_correct():
    p = DeterministicTestProvider()
    a, b = await p.embed(["alpha", "alpha"]), await p.embed(["beta"])
    assert a[0] == a[1] and a[0] != b[0] and len(a[0]) == DIM
    assert sum(x * x for x in a[0]) == pytest.approx(1.0)


def test_check_dimensions_never_truncates_or_pads():
    with pytest.raises(DimensionMismatch, match="never truncate"):
        check_dimensions([[0.1] * (DIM + 1)], DIM, 1)
    with pytest.raises(DimensionMismatch):
        check_dimensions([[0.1] * (DIM - 1)], DIM, 1)
    with pytest.raises(EmbeddingError, match="2 vectors for 1"):
        check_dimensions([[0.0] * DIM, [0.0] * DIM], DIM, 1)
    with pytest.raises(EmbeddingError, match="non-finite"):
        check_dimensions([[float("nan")] + [0.0] * (DIM - 1)], DIM, 1)
    check_dimensions([[0.0] * DIM], DIM, 1)


def test_provider_selection_and_production_guard(monkeypatch):
    assert get_provider("test").name == "test" and get_provider("openai").name == "openai"
    with pytest.raises(EmbeddingError, match="unknown"):
        get_provider("magic")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(EmbeddingError, match="not allowed in production"):
        get_provider("test")


def openai_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_openai_provider_request_shape_and_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["auth"], seen["body"] = req.headers["authorization"], req.read()
        import json
        n = len(json.loads(seen["body"])["input"])
        # returned out of order on purpose
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [float(i)] * 8} for i in reversed(range(n))]})

    p = OpenAIProvider(api_key="sk-test", model="text-embedding-3-large", dimension=8, client=openai_client(handler))
    vecs = await p.embed(["a", "b", "c"])
    assert [v[0] for v in vecs] == [0.0, 1.0, 2.0]               # re-ordered by index
    import json
    sent = json.loads(seen["body"])
    assert seen["auth"] == "Bearer sk-test" and sent["dimensions"] == 8 and sent["model"] == "text-embedding-3-large"


async def test_openai_provider_error_classification():
    async def call(status, headers=None, key="k"):
        p = OpenAIProvider(api_key=key, dimension=8, client=openai_client(lambda r: httpx.Response(status, headers=headers or {}, json={})))
        with pytest.raises(EmbeddingError) as e:
            await p.embed(["x"])
        return e.value

    assert (await call(429, {"retry-after": "3"})).retry_after == 3.0 and (await call(429)).retryable
    assert (await call(503)).retryable
    assert not (await call(401)).retryable and not (await call(400)).retryable
    assert "EMBEDDING_API_KEY" in str(await call(200, key=""))
    wrong = OpenAIProvider(api_key="k", dimension=8, client=openai_client(
        lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0] * 5}]})))
    with pytest.raises(DimensionMismatch):
        await wrong.embed(["x"])


class ScriptedProvider:
    """Fails according to a script, then delegates to the deterministic provider."""
    name, model = "scripted", "scripted-v1"

    def __init__(self, script=(), dimension=DIM):
        self.script, self.dimension, self.calls = list(script), dimension, 0
        self._real = DeterministicTestProvider(dimension, "scripted-v1")

    async def embed(self, texts):
        self.calls += 1
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
        return await self._real.embed(texts)


async def no_sleep(_):
    return None


async def test_retry_honours_retry_after_and_gives_up_on_permanent_errors():
    waits = []

    async def rec(s):
        waits.append(s)

    p = ScriptedProvider([EmbeddingError("rl", retryable=True, retry_after=7), EmbeddingError("net", retryable=True)])
    out = await emb.embed_with_retry(p, ["x"], rec)
    assert len(out) == 1 and p.calls == 3 and waits[0] == 7 and waits[1] == 1.0     # backoff doubles after the first wait
    bad = ScriptedProvider([EmbeddingError("forbidden")])
    with pytest.raises(EmbeddingError):
        await emb.embed_with_retry(bad, ["x"], no_sleep)
    assert bad.calls == 1                                                          # not retried
    always = ScriptedProvider([EmbeddingError("down", retryable=True)] * 10)
    with pytest.raises(EmbeddingError):
        await emb.embed_with_retry(always, ["x"], no_sleep)
    assert always.calls == emb.MAX_ATTEMPTS
    mism = ScriptedProvider([DimensionMismatch("bad dims", retryable=True)])
    with pytest.raises(DimensionMismatch):
        await emb.embed_with_retry(mism, ["x"], no_sleep)
    assert mism.calls == 1                                                         # dimension errors are never retried


# -- database ---------------------------------------------------------------------------------------
@pytest.fixture
async def chunks(conn):
    doc = await conn.fetchval("INSERT INTO documents.document (title,document_type,file_hash,status) VALUES ('Emb doc','Notice',$1,'active') RETURNING document_id", uuid.uuid4().hex)
    ids = []
    for i in range(5):
        ids.append(await conn.fetchval("INSERT INTO documents.document_chunk (document_id,chunk_number,content,page_number) VALUES ($1,$2,$3,1) RETURNING chunk_id", doc, i, f"Chunk text number {i} about schemes"))
    yield doc, ids
    await conn.execute("DELETE FROM documents.document WHERE document_id=$1", doc)


async def state(conn, ids):
    return {r["chunk_id"]: r for r in await conn.fetch("SELECT chunk_id, embedding IS NOT NULL has, embedding_model, embedded_text_hash, embedding_error FROM documents.document_chunk WHERE chunk_id = ANY($1)", ids)}


@pytest.mark.db
async def test_embeds_new_chunks_with_model_and_text_hash_then_is_idempotent(conn, chunks):
    doc, ids = chunks
    p = ScriptedProvider()
    stats = await emb.embed_chunks(conn, p, batch_size=2, sleep=no_sleep)
    assert stats["embedded"] >= 5 and stats["failed"] == 0
    st = await state(conn, ids)
    assert all(s["has"] and s["embedding_model"] == "scripted-v1" and s["embedding_error"] is None for s in st.values())
    assert await conn.fetchval("SELECT vector_dims(embedding) FROM documents.document_chunk WHERE chunk_id=$1", ids[0]) == DIM
    calls = p.calls
    again = await emb.embed_chunks(conn, p, sleep=no_sleep)
    assert again["selected"] == 0 and p.calls == calls                              # nothing to do -> no provider calls


@pytest.mark.db
async def test_vector_search_returns_the_identical_text_first(conn, chunks):
    doc, ids = chunks
    p = ScriptedProvider()
    await emb.embed_chunks(conn, p, sleep=no_sleep)
    q = emb.to_vector_literal((await p.embed(["Chunk text number 3 about schemes"]))[0])
    top = await conn.fetchrow("SELECT chunk_id, 1-(embedding <=> $1::vector) AS sim FROM documents.document_chunk WHERE embedding IS NOT NULL ORDER BY embedding <=> $1::vector LIMIT 1", q)
    assert top["chunk_id"] == ids[3] and top["sim"] == pytest.approx(1.0, abs=1e-5)


@pytest.mark.db
async def test_changed_text_and_changed_model_trigger_reembedding(conn, chunks):
    doc, ids = chunks
    p = ScriptedProvider()
    await emb.embed_chunks(conn, p, sleep=no_sleep)
    before = (await state(conn, ids))[ids[1]]["embedded_text_hash"]
    await conn.execute("UPDATE documents.document_chunk SET content='Edited content for chunk one' WHERE chunk_id=$1", ids[1])
    s = await emb.embed_chunks(conn, p, sleep=no_sleep)
    assert s["embedded"] == 1                                                       # only the edited chunk
    assert (await state(conn, ids))[ids[1]]["embedded_text_hash"] != before
    other = ScriptedProvider()
    other.model = "scripted-v2"
    s2 = await emb.embed_chunks(conn, other, sleep=no_sleep)
    assert s2["embedded"] >= 5 and all(v["embedding_model"] == "scripted-v2" for v in (await state(conn, ids)).values())
    s3 = await emb.embed_chunks(conn, other, reembed=True, sleep=no_sleep)
    assert s3["embedded"] >= 5                                                      # forced


@pytest.mark.db
async def test_partial_failure_marks_only_the_failed_batch_and_retry_recovers(conn, chunks):
    doc, ids = chunks
    # batch size 2 -> 3 batches; the 2nd batch fails permanently
    p = ScriptedProvider([None, EmbeddingError("quota exceeded")])
    stats = await emb.embed_chunks(conn, p, batch_size=2, sleep=no_sleep)
    assert stats["failed"] == 2 and stats["embedded"] >= 3
    st = await state(conn, ids)
    failed = [s for s in st.values() if s["embedding_error"]]
    assert len(failed) == 2 and all(not s["has"] and "quota" in s["embedding_error"] for s in failed)
    assert sum(1 for s in st.values() if s["has"]) == 3                             # the other batches were stored
    fixed = await emb.embed_chunks(conn, ScriptedProvider(), sleep=no_sleep)
    assert fixed["embedded"] == 2
    assert all(s["has"] and s["embedding_error"] is None for s in (await state(conn, ids)).values())


@pytest.mark.db
async def test_wrong_dimension_is_rejected_and_nothing_is_stored(conn, chunks):
    doc, ids = chunks
    p = ScriptedProvider(dimension=DIM - 10)
    stats = await emb.embed_chunks(conn, p, sleep=no_sleep)
    assert stats["failed"] >= 5 and stats["embedded"] == 0
    st = await state(conn, ids)
    assert all(not s["has"] and "dimensions" in s["embedding_error"] for s in st.values())


@pytest.mark.db
async def test_catalogue_embedding_covers_schemes_and_services(conn):
    p = ScriptedProvider()
    try:
        s = await emb.embed_catalogue(conn, p, "schemes.scheme", sleep=no_sleep)
        v = await emb.embed_catalogue(conn, p, "services.service", sleep=no_sleep)
        assert s["embedded"] == 12 and v["embedded"] == 10 and s["failed"] == v["failed"] == 0
        assert (await emb.embed_catalogue(conn, p, "schemes.scheme", sleep=no_sleep))["selected"] == 0
        with pytest.raises(ValueError):
            await emb.embed_catalogue(conn, p, "identity.citizen")
    finally:
        await conn.execute("UPDATE schemes.scheme SET embedding=NULL")
        await conn.execute("UPDATE services.service SET embedding=NULL")


@pytest.mark.db
async def test_cli_main_reports_and_checks_column_dimension(test_db_dsn, chunks, capsys):
    rc = await emb.main(["--documents", "--provider", "test", "--dsn", test_db_dsn])
    assert rc == 0 and "'embedded'" in capsys.readouterr().out
