"""Hybrid retrieval and the OpenAI-compatible chat, against a real Postgres."""

import asyncio
import hashlib
import json
import uuid

import psycopg
import pytest
from core_api_helpers import (
    add_member,
    as_user,
    bearer,
    new_key,
    new_workspace,
    unit,
)
from psycopg_pool import AsyncConnectionPool

from core_api.adapters.postgres import PostgresStore
from core_api.domain.retrieval import ChatMessage, Hit, build_messages, citations_for, fuse, rrf
from ldk_core.errors import ErrorCode, ServiceError

QUESTION = "When does BLUEFIN-42 ship?"


def vec(v):
    return "[" + ",".join(str(x) for x in v) + "]"


def seed(db_url, ws, chunks, title="memo.pdf"):
    """Insert one ready document with ``chunks`` = [(text, vector, page)]; return chunk ids."""
    with psycopg.connect(db_url, autocommit=True) as conn:
        (doc,) = conn.execute(
            """INSERT INTO core.documents
                   (workspace_id, source_type, source_uri, title, content_hash, status, created_by)
               VALUES (%s, 'upload', 'upload:x', %s, %s, 'ready', 'alice') RETURNING id""",
            (ws, title, hashlib.sha256(uuid.uuid4().bytes).digest()),
        ).fetchone()
        ids = []
        for ord_, (text, vector, page) in enumerate(chunks):
            (cid,) = conn.execute(
                """INSERT INTO core.chunks
                       (document_id, workspace_id, ord, text, page, embedding, embed_model)
                   VALUES (%s, %s, %s, %s, %s, %s::vector, 'fake-embed') RETURNING id""",
                (doc, ws, ord_, text, page, vec(vector)),
            ).fetchone()
            ids.append(cid)
        return ids


def search(db_url, ws, text, vector, k=10):
    async def run():
        async with AsyncConnectionPool(db_url, min_size=1, max_size=2) as pool:
            return await PostgresStore(pool).search(uuid.UUID(ws), text=text, vector=vector, k=k)

    return asyncio.run(run())


def ask(client, headers, question=QUESTION, **body):
    return client.post(
        "/v1/chat/completions",
        json={"model": "llama3.1", "messages": [{"role": "user", "content": question}], **body},
        headers=headers,
    )


def user_in(issuer, ws, sub="alice"):
    return {**as_user(issuer, sub), "X-Workspace-Id": ws}


# ------------------------------------------------------------ pure domain


def test_rrf_rewards_agreement_between_lists() -> None:
    fused = rrf([["a", "b", "c"], ["c", "d"]])
    order = [item for item, _ in fused]
    assert order[0] == "c"  # 3rd in one list and 1st in the other beats 1st in one only
    assert set(order) == {"a", "b", "c", "d"}
    assert dict(fused)["c"] == pytest.approx(1 / 63 + 1 / 61)


def test_fuse_keeps_the_best_and_numbers_citations() -> None:
    hit = lambda n: Hit(uuid.uuid4(), uuid.uuid4(), f"doc{n}", n, f"text {n}")  # noqa: E731
    a, b, c = hit(1), hit(2), hit(3)
    best = fuse([a, b], [b, c], limit=2)
    assert best[0] is b
    assert [x.index for x in citations_for(best)] == [1, 2]


def test_the_prompt_is_grounded_only_when_there_are_sources() -> None:
    sources = citations_for([Hit(uuid.uuid4(), uuid.uuid4(), "memo.pdf", 2, "Ships on 14 March.")])
    messages = build_messages(
        [ChatMessage("user", "hi"), ChatMessage("assistant", "hello")], "When?", sources
    )
    assert messages[0].role == "system"
    assert "[1] memo.pdf, page 2" in messages[0].content
    assert [m.role for m in messages[1:]] == ["user", "assistant", "user"]
    assert build_messages([], "When?", [])[0].role == "user"  # no sources: plain assistant


# ----------------------------------------------------------- the database


def test_a_workspace_never_retrieves_another_workspaces_chunks(client, issuer, db_url) -> None:
    """Mandatory: B holds a perfect match for the question, in text and vector."""
    a = new_workspace(client, issuer, sub="alice", slug="a")
    b = new_workspace(client, issuer, sub="bob", slug="b")
    empty = new_workspace(client, issuer, sub="carol", slug="c")
    (mine,) = seed(db_url, a, [("Alpha team notes about lunch.", unit(5), 1)])
    seed(db_url, b, [(QUESTION + " It ships on 14 March.", unit(0), 1)])

    semantic, lexical = search(db_url, a, QUESTION, unit(0))
    assert {h.chunk_id for h in semantic + lexical} == {mine}
    assert search(db_url, empty, QUESTION, unit(0)) == ([], [])


def test_chat_never_cites_or_sends_another_workspaces_text(
    client, issuer, db_url, model_client
) -> None:
    a = new_workspace(client, issuer, sub="alice", slug="a")
    b = new_workspace(client, issuer, sub="bob", slug="b")
    seed(db_url, a, [("Alpha team notes about lunch.", unit(5), 1)])
    seed(db_url, b, [("SECRET-B: BLUEFIN-42 ships on 14 March.", unit(0), 1)])

    res = ask(client, user_in(issuer, a))
    assert res.status_code == 200
    assert all("SECRET-B" not in c["snippet"] for c in res.json()["citations"])
    sent = " ".join(m.content for m in model_client.sent[-1])
    assert "SECRET-B" not in sent
    # And a key from workspace A cannot point itself at B.
    key = new_key(client, issuer, a)["key"]
    assert ask(client, {**bearer(key), "X-Workspace-Id": b}).status_code == 403


def test_hybrid_search_finds_exact_terms_and_meaning(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    exact, meaning, both = seed(
        db_url,
        ws,
        [
            ("BLUEFIN-42 is the codename for the search rewrite.", unit(9), 1),  # words only
            ("The launch is planned for mid-March.", unit(0), 2),  # meaning only
            ("BLUEFIN-42 ships on 14 March.", unit(0), 3),  # both
        ],
    )
    semantic, lexical = search(db_url, ws, "BLUEFIN-42 ship date", unit(0))
    assert exact in {h.chunk_id for h in lexical}
    assert meaning in {h.chunk_id for h in semantic}
    fused = fuse(semantic, lexical, limit=3)
    assert fused[0].chunk_id == both
    assert {h.chunk_id for h in fused} == {exact, meaning, both}


# --------------------------------------------------------------- the API


def test_an_answer_carries_citations_and_its_provenance(
    client, issuer, db_url, model_client
) -> None:
    ws = new_workspace(client, issuer)
    (chunk,) = seed(db_url, ws, [("BLUEFIN-42 ships on 14 March.", unit(0), 3)], title="launch.pdf")

    res = ask(client, user_in(issuer, ws))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["object"] == "chat.completion"
    assert "14 March [1]" in body["choices"][0]["message"]["content"]
    (citation,) = body["citations"]
    assert citation | {"chunk_id": None} == {
        "index": 1,
        "chunk_id": None,
        "document_id": citation["document_id"],
        "title": "launch.pdf",
        "page": 3,
        "snippet": "BLUEFIN-42 ships on 14 March.",
    }
    assert citation["chunk_id"] == str(chunk)
    assert body["usage"]["prompt_tokens"] == 42

    caller = model_client.callers[-1]
    assert (caller.user_id, str(caller.workspace_id)) == ("alice", ws)

    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT role, retrieved_chunk_ids, tokens_in, model FROM core.messages"
            " ORDER BY created_at, role DESC"
        ).fetchall()
    assert rows[0][0] == "user"
    assert rows[1] == ("assistant", [chunk], 42, "llama3.1")


def test_streaming_ends_with_citations_then_done(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    seed(db_url, ws, [("BLUEFIN-42 ships on 14 March.", unit(0), 1)])
    res = ask(client, user_in(issuer, ws), stream=True)
    assert res.headers["content-type"].startswith("text/event-stream")
    events = [line[6:] for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert "14 March [1]" in text
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert [c["index"] for c in chunks[-1]["citations"]] == [1]


def test_a_failure_mid_stream_is_reported_in_band(client, issuer, model_client) -> None:
    ws = new_workspace(client, issuer)

    async def failing(messages, *, model, caller):
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "model went away")
        yield  # makes this an async generator

    model_client.stream_chat = failing
    res = ask(client, user_in(issuer, ws), stream=True)
    events = [line[6:] for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    assert json.loads(events[-2]) == {
        "error": {"code": "upstream_unavailable", "message": "model went away"}
    }


def test_models_are_listed_in_openai_format(client, issuer) -> None:
    ws = new_workspace(client, issuer)
    res = client.get("/v1/models", headers=user_in(issuer, ws))
    assert [m["id"] for m in res.json()["data"]] == ["llama3.1", "qwen2.5"]


def test_readers_can_chat_and_bad_requests_are_400(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    add_member(db_url, ws, "rita-reader", "reader")
    assert ask(client, user_in(issuer, ws, sub="rita-reader")).status_code == 200
    res = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "assistant", "content": "hi"}]},
        headers=user_in(issuer, ws),
    )
    assert res.status_code == 400
    assert ask(client, user_in(issuer, ws), question="   ").status_code == 400


def test_a_conversation_id_groups_exchanges(client, issuer, db_url) -> None:
    ws = new_workspace(client, issuer)
    headers = {**user_in(issuer, ws), "X-Conversation-Id": "chat-123"}
    ask(client, headers)
    ask(client, headers, question="And who owns it?")
    ask(client, user_in(issuer, ws))  # no id: a conversation of its own
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT external_id,"
            " (SELECT count(*) FROM core.messages m WHERE m.conversation_id = c.id)"
            " FROM core.conversations c ORDER BY external_id NULLS LAST"
        ).fetchall()
    assert rows == [("chat-123", 4), (None, 2)]


def test_the_question_is_what_gets_embedded(client, issuer, embedder) -> None:
    ws = new_workspace(client, issuer)
    calls_before = embedder.calls
    ask(client, user_in(issuer, ws))
    assert embedder.calls == calls_before + 1
