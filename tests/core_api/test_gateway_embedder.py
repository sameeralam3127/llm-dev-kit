"""The worker's model-gateway client."""

import asyncio
import json

import httpx
import pytest

from ingest_worker.gateway import GatewayEmbedder
from ldk_core.errors import ErrorCode, ServiceError


def embedder(handler):
    return GatewayEmbedder(
        "http://gw.test",
        "svc-token",
        model="nomic-embed-text",
        dimension=3,
        transport=httpx.MockTransport(handler),
    )


def test_sends_the_service_token_and_model() -> None:
    seen = {}

    def handle(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [[1, 2, 3], [4, 5, 6]]})

    assert asyncio.run(embedder(handle).embed(["a", "b"])) == [[1, 2, 3], [4, 5, 6]]
    assert seen == {
        "auth": "Bearer svc-token",
        "body": {"texts": ["a", "b"], "model": "nomic-embed-text"},
    }


def test_refuses_wrong_dimensions_and_maps_failures() -> None:
    with pytest.raises(ServiceError) as caught:
        asyncio.run(
            embedder(lambda r: httpx.Response(200, json={"embeddings": [[1, 2]]})).embed(["a"])
        )
    assert caught.value.code is ErrorCode.UPSTREAM_ERROR

    def down(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ServiceError) as caught:
        asyncio.run(embedder(down).embed(["a"]))
    assert caught.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
