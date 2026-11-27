"""Core API and worker clients for model-gateway."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from core_api.adapters.gateway import GatewayEmbedder, GatewayModelClient
from core_api.ports.models import OnBehalfOf
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


@pytest.mark.parametrize(
    ("status", "code", "message"),
    [
        (403, ErrorCode.FORBIDDEN, "model-gateway request failed (HTTP 403)"),
        (200, ErrorCode.UPSTREAM_UNAVAILABLE, "model-gateway stream failed"),
    ],
)
def test_chat_client_keeps_error_code_and_omits_gateway_details(status, code, message) -> None:
    body = {"error": {"code": "upstream_unavailable", "message": "synthetic-gateway-detail"}}

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=f"data: {json.dumps(body)}\n\n")

    async def check() -> None:
        client = GatewayModelClient(
            "http://gw.test", "svc-token", transport=httpx.MockTransport(handle)
        )
        try:
            with pytest.raises(ServiceError) as caught:
                async for _ in client.stream_chat(
                    [], model="test-model", caller=OnBehalfOf("test-user", uuid4())
                ):
                    pass
            assert caught.value.code is code
            assert caught.value.message == message
        finally:
            await client.aclose()

    asyncio.run(check())
