"""Ingestion end to end: upload → queue → worker → chunks, against a real Postgres."""

import asyncio
import hashlib
import itertools
from contextlib import asynccontextmanager

import psycopg
from core_api_helpers import FakeEmbedder, add_member, as_user, bearer, new_key, new_workspace
from pdfs import make_pdf
from psycopg_pool import AsyncConnectionPool

from core_api.adapters.postgres import PostgresStore
from ingest_worker.pipeline import process_next
from ldk_core.errors import ErrorCode, ServiceError
from ldk_plugin_chunker_fixed import FixedWindowChunker
from ldk_plugin_loader_pdf import PdfLoader

# Long enough to make several chunks with the default 500-character window.
LONG_TEXT = " ".join(f"Sentence {i} about the BLUEFIN-42 launch on 14 March." for i in range(60))


UNAVAILABLE = ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "model-gateway unreachable")


@asynccontextmanager
async def store_for(db_url):
    async with AsyncConnectionPool(db_url, min_size=1, max_size=8) as pool:
        yield PostgresStore(pool)


async def work(db_url, embedder=None, *, worker_id="w1", batch_size=32):
    async with store_for(db_url) as store:
        return await process_next(
            queue=store,
            store=store,
            loader=PdfLoader(),
            chunker=FixedWindowChunker(),
            embedder=embedder or FakeEmbedder(),
            worker_id=worker_id,
            batch_size=batch_size,
            rand=lambda: 0.0,
        )


def upload(client, issuer, ws, data, sub="alice"):
    return client.post(
        "/api/v1/documents",
        files={"file": ("memo.pdf", data, "application/pdf")},
        headers={**as_user(issuer, sub), "X-Workspace-Id": ws},
    )


def sql(db_url, query, *params):
    with psycopg.connect(db_url, autocommit=True) as conn:
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else None


# ------------------------------------------------------------ happy path


def test_an_upload_is_queued_and_the_worker_indexes_it(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    res = upload(client, issuer, ws, make_pdf([LONG_TEXT]))
    assert res.status_code == 202, res.text
    doc = res.json()["data"]
    assert doc["status"] == "pending"

    assert asyncio.run(work(db_url)) == "succeeded"
    assert asyncio.run(work(db_url)) is None  # nothing left to do

    listed = client.get(
        "/api/v1/documents", headers={**as_user(issuer, "alice"), "X-Workspace-Id": ws}
    )
    (row,) = listed.json()["data"]
    assert row["status"] == "ready"
    assert row["chunk_count"] > 1
    ((workspaces,),) = sql(
        db_url,
        "SELECT array_agg(DISTINCT workspace_id::text) FROM core.chunks WHERE document_id = %s",
        doc["id"],
    )
    assert workspaces == [ws]


# -------------------------------------------------------------- mandatory


def test_reingesting_the_same_file_creates_no_duplicate_chunks(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    pdf = make_pdf([LONG_TEXT])
    first = upload(client, issuer, ws, pdf)
    assert asyncio.run(work(db_url)) == "succeeded"
    ((before,),) = sql(db_url, "SELECT count(*) FROM core.chunks")

    # 1. Uploading the same bytes again is a no-op: same document, no new job.
    again = upload(client, issuer, ws, pdf)
    assert again.status_code == 200
    assert again.json()["duplicate"] is True
    assert again.json()["data"]["id"] == first.json()["data"]["id"]
    assert sql(db_url, "SELECT count(*) FROM core.ingestion_jobs") == [(1,)]

    # 2. Re-indexing the document replaces its chunks rather than adding to them.
    sql(
        db_url,
        "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)",
        first.json()["data"]["id"],
        ws,
    )
    assert asyncio.run(work(db_url)) == "succeeded"
    assert sql(db_url, "SELECT count(*) FROM core.chunks") == [(before,)]
    assert sql(db_url, "SELECT count(*), count(DISTINCT ord) FROM core.chunks") == [
        (before, before)
    ]


def test_a_failing_job_retries_with_backoff_then_lands_in_failed(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    doc = upload(client, issuer, ws, make_pdf([LONG_TEXT])).json()["data"]
    embedder = FakeEmbedder(fail=UNAVAILABLE)

    delays = []
    for attempt in range(1, 5):
        assert asyncio.run(work(db_url, embedder)) == "retrying"
        ((state, attempts, wait, error),) = sql(
            db_url,
            """SELECT state, attempts, extract(epoch FROM run_after - now()), last_error
               FROM core.ingestion_jobs""",
        )
        assert (state, attempts) == ("queued", attempt)
        assert "model-gateway unreachable" in error
        delays.append(float(wait))
        # Not due yet, so nothing is claimed...
        assert asyncio.run(work(db_url, embedder)) is None
        # ...until the backoff has passed.
        sql(db_url, "UPDATE core.ingestion_jobs SET run_after = now()")

    # Each wait at least doubles (10 s * 2^n, scaled by jitter; jitter is 0.5 here).
    assert all(b >= a * 1.9 for a, b in itertools.pairwise(delays))

    assert asyncio.run(work(db_url, embedder)) == "failed"
    ((state, attempts, error),) = sql(
        db_url, "SELECT state, attempts, last_error FROM core.ingestion_jobs"
    )
    assert (state, attempts) == ("failed", 5)
    assert error
    assert sql(db_url, "SELECT status FROM core.documents WHERE id = %s", doc["id"]) == [
        ("failed",)
    ]
    listed = client.get(
        "/api/v1/documents", headers={**as_user(issuer, "alice"), "X-Workspace-Id": ws}
    )
    assert "model-gateway unreachable" in listed.json()["data"][0]["last_error"]


# ------------------------------------------------------------ robustness


def test_an_unreadable_file_fails_at_once_without_retries(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    assert upload(client, issuer, ws, b"%PDF-1.4 this is not really a pdf").status_code == 202
    assert asyncio.run(work(db_url)) == "failed"
    assert sql(db_url, "SELECT state, attempts FROM core.ingestion_jobs") == [("failed", 1)]


def test_a_failed_reindex_leaves_the_old_chunks_untouched(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    doc = upload(client, issuer, ws, make_pdf([LONG_TEXT])).json()["data"]
    assert asyncio.run(work(db_url)) == "succeeded"
    before = sql(db_url, "SELECT id, text FROM core.chunks ORDER BY ord")

    sql(
        db_url,
        "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)",
        doc["id"],
        ws,
    )
    # Fail halfway: the first batch embeds, the second does not.
    assert (
        asyncio.run(work(db_url, FakeEmbedder(fail=UNAVAILABLE, ok_calls=1), batch_size=1))
        == "retrying"
    )
    assert sql(db_url, "SELECT id, text FROM core.chunks ORDER BY ord") == before


def test_skip_locked_gives_every_job_to_exactly_one_worker(db_url) -> None:
    async def scenario():
        async with store_for(db_url) as store:
            ws = (await store.create_workspace(slug="busy", name="Busy", owner_id="alice")).id
            for i in range(20):
                data = f"%PDF-{i}".encode()
                await store.create_upload(
                    workspace_id=ws,
                    user_id="alice",
                    filename=f"{i}.pdf",
                    media_type="application/pdf",
                    data=data,
                    content_hash=hashlib.sha256(data).digest(),
                )

            async def worker(name):
                claimed = []
                while (job := await store.claim(name)) is not None:
                    claimed.append(job.id)
                    await asyncio.sleep(0)  # let the other workers interleave
                return claimed

            return await asyncio.gather(*(worker(f"w{i}") for i in range(5)))

    results = asyncio.run(scenario())
    every = [job for claimed in results for job in claimed]
    assert len(every) == 20
    assert len(set(every)) == 20  # nobody got a job twice
    assert sum(1 for claimed in results if claimed) > 1  # the work was shared


def test_an_expired_lease_returns_the_job_and_fences_the_old_worker(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    upload(client, issuer, ws, make_pdf([LONG_TEXT]))

    async def scenario():
        async with store_for(db_url) as store:
            stalled = await store.claim("worker-a")
            await asyncio.to_thread(
                sql, db_url, "UPDATE core.ingestion_jobs SET locked_at = now() - interval '1 hour'"
            )
            assert await store.reclaim_expired(lease_seconds=60) == 1
            assert await store.claim("worker-b") is not None
            # worker-a comes back from its stall: its write must be refused.
            assert await store.replace_chunks(stalled, [], "fake-embed") is False

    asyncio.run(scenario())
    assert sql(db_url, "SELECT state, locked_by, attempts FROM core.ingestion_jobs") == [
        ("running", "worker-b", 2)
    ]
    assert sql(db_url, "SELECT count(*) FROM core.chunks") == [(0,)]


# ------------------------------------------------------------- the API


def test_only_editors_and_owners_can_upload(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    add_member(db_url, ws, "rita-reader", "reader")
    add_member(db_url, ws, "ed-editor", "editor")
    pdf = make_pdf(["hello"])
    assert upload(client, issuer, ws, pdf, sub="rita-reader").status_code == 403
    assert upload(client, issuer, ws, pdf, sub="ed-editor").status_code == 202
    assert upload(client, issuer, ws, make_pdf(["x"]), sub="mallory").status_code == 403


def test_only_pdfs_are_accepted(client, issuer) -> None:
    ws = new_workspace(client, issuer)
    res = upload(client, issuer, ws, b"just text pretending", sub="alice")
    assert res.status_code == 400


def test_the_workspace_must_be_chosen_when_there_are_several(client, issuer) -> None:
    a = new_workspace(client, issuer, slug="a")
    new_workspace(client, issuer, slug="b")
    res = client.post(
        "/api/v1/documents",
        files={"file": ("m.pdf", make_pdf(["x"]), "application/pdf")},
        headers=as_user(issuer, "alice"),
    )
    assert res.status_code == 400
    assert "X-Workspace-Id" in res.json()["error"]["message"]
    # An API key carries its workspace, so it needs no header.
    key = new_key(client, issuer, a, scopes=("chat", "ingest"))["key"]
    res = client.post(
        "/api/v1/documents",
        files={"file": ("m.pdf", make_pdf(["x"]), "application/pdf")},
        headers=bearer(key),
    )
    assert res.status_code == 202
    assert res.json()["data"]["workspace_id"] == a


def test_listing_never_shows_another_workspaces_documents(client, issuer) -> None:
    mine = new_workspace(client, issuer, sub="alice", slug="mine")
    theirs = new_workspace(client, issuer, sub="bob", slug="theirs")
    upload(client, issuer, mine, make_pdf(["alice's notes"]), sub="alice")
    upload(client, issuer, theirs, make_pdf(["bob's notes"]), sub="bob")
    listed = client.get(
        "/api/v1/documents", headers={**as_user(issuer, "bob"), "X-Workspace-Id": theirs}
    )
    assert [d["workspace_id"] for d in listed.json()["data"]] == [theirs]
    peek = client.get(
        "/api/v1/documents", headers={**as_user(issuer, "bob"), "X-Workspace-Id": mine}
    )
    assert peek.status_code == 403
