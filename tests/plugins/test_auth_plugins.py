"""The auth plugins against real RS256 tokens, and the Authenticator over them."""

import asyncio
import time

import httpx
import jwt
import pytest
from identity import AUDIENCE, ISSUER, JWKS_URL, TOKEN_URL, Issuer, public_jwk, sign

from ldk_core.auth import ANONYMOUS, Authenticator, require_scope
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import AUTH, PluginKind, PluginRegistry
from ldk_plugin_auth import LocalAuthProvider, OidcAuthProvider, local_plugin, oidc_plugin


def run(coro):
    return asyncio.run(coro)


def rejected(coro) -> ServiceError:
    with pytest.raises(ServiceError) as caught:
        run(coro)
    return caught.value


@pytest.fixture
def issuer() -> Issuer:
    return Issuer()


# --------------------------------------------------------------- auth.local


def test_a_valid_token_becomes_a_principal(issuer: Issuer) -> None:
    token = issuer.token("user", sub="u-7")
    principal = run(issuer.provider().authenticate(token))

    assert principal.subject == "u-7"
    assert principal.kind == "user"
    assert principal.roles == {"user"}
    assert principal.scopes == {"chat", "ingest"}
    assert principal.credential == token


def test_a_token_cannot_grant_more_than_its_role(issuer: Issuer) -> None:
    token = issuer.token("viewer", scope="chat ingest admin")
    assert run(issuer.provider().authenticate(token)).scopes == {"chat"}


def test_a_token_can_narrow_its_role(issuer: Issuer) -> None:
    token = issuer.token("admin", scope="chat")
    assert run(issuer.provider().authenticate(token)).scopes == {"chat"}


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"expires_in": -120},
        {"audience": "someone-else"},
    ],
    ids=["expired", "wrong-audience"],
)
def test_invalid_tokens_are_401(issuer: Issuer, token_kwargs) -> None:
    error = rejected(issuer.provider().authenticate(issuer.token(**token_kwargs)))
    assert error.code is ErrorCode.UNAUTHORIZED
    # Never says which check failed.
    assert error.message == "Authentication required"


def test_a_tampered_token_is_401(issuer: Issuer) -> None:
    header, payload, signature = issuer.token("viewer").split(".")
    forged_payload = jwt.utils.base64url_encode(
        jwt.utils.base64url_decode(payload).replace(b'"viewer"', b'"admin"')
    ).decode()
    error = rejected(issuer.provider().authenticate(f"{header}.{forged_payload}.{signature}"))
    assert error.code is ErrorCode.UNAUTHORIZED


def test_symmetric_and_unsigned_tokens_are_401(issuer: Issuer) -> None:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "x", "iat": now, "exp": now + 60}
    # HS256 signed with the public key as the secret: the classic confusion attack.
    hmac = jwt.encode(
        claims,
        "public-key-used-as-an-hmac-secret-0123456789",
        algorithm="HS256",
        headers={"kid": "key-1"},
    )
    unsigned = jwt.encode(claims, None, algorithm="none")
    provider = issuer.provider()
    for token in (hmac, unsigned):
        assert rejected(provider.authenticate(token)).code is ErrorCode.UNAUTHORIZED


def test_rotation_is_picked_up_and_unknown_keys_are_not_refetched_in_a_loop(
    issuer: Issuer,
) -> None:
    provider = issuer.provider()

    async def scenario() -> None:
        await provider.authenticate(issuer.token())
        assert issuer.jwks_fetches == 1

        # The web app rotates; a token signed with the new key refetches once.
        issuer.rotate("key-2")
        provider._keys._fetched_at -= 60  # past the minimum refetch interval
        await provider.authenticate(issuer.token(kid="key-2"))
        assert issuer.jwks_fetches == 2

        # A made-up key id does not trigger another fetch straight away.
        forged = sign({"iss": ISSUER, "aud": AUDIENCE, "sub": "x"}, "key-3")
        with pytest.raises(ServiceError):
            await provider.authenticate(forged)
        assert issuer.jwks_fetches == 2

    run(scenario())


def test_an_unreachable_identity_service_is_503(issuer: Issuer) -> None:
    issuer.down = True
    error = rejected(issuer.provider().authenticate(issuer.token()))
    assert error.code is ErrorCode.UPSTREAM_UNAVAILABLE


def test_api_keys_are_exchanged_and_cached(issuer: Issuer) -> None:
    issuer.api_keys["sk-ldk-abcd1234"] = "viewer"
    provider = issuer.provider()

    async def twice():
        first = await provider.authenticate("sk-ldk-abcd1234")
        second = await provider.authenticate("sk-ldk-abcd1234")
        return first, second

    first, second = run(twice())
    assert first.kind == "api_key"
    assert first.subject == "owner-of-1234"
    assert first.scopes == {"chat"}
    # The exchanged token, not the key, is what gets forwarded.
    assert first.credential and first.credential.count(".") == 2
    assert second is first
    assert issuer.exchanges == 1


def test_an_unknown_api_key_is_401(issuer: Issuer) -> None:
    error = rejected(issuer.provider().authenticate("sk-ldk-revoked"))
    assert error.code is ErrorCode.UNAUTHORIZED


def test_an_api_key_exchange_without_the_web_app_is_503(issuer: Issuer) -> None:
    issuer.api_keys["sk-ldk-abcd1234"] = "user"
    issuer.down = True
    error = rejected(issuer.provider().authenticate("sk-ldk-abcd1234"))
    assert error.code is ErrorCode.UPSTREAM_UNAVAILABLE


def test_local_accepts_only_its_own_credentials(issuer: Issuer) -> None:
    provider = issuer.provider()
    assert provider.accepts("sk-ldk-anything")
    assert provider.accepts(issuer.token())
    assert not provider.accepts(issuer.token(issuer="https://keycloak.test/realms/x"))
    assert not provider.accepts("sk-local-placeholder")
    assert not provider.accepts("not.a.jwt")


# ---------------------------------------------------------------- auth.oidc

KC_ISSUER = "http://localhost:8080/sso/realms/llm-dev-kit"
KC_DISCOVERY = "http://keycloak:8080/sso/realms/llm-dev-kit/.well-known/openid-configuration"
KC_JWKS = "http://keycloak:8080/sso/realms/llm-dev-kit/protocol/openid-connect/certs"


def keycloak(discovery_issuer: str = KC_ISSUER) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if str(request.url) == KC_DISCOVERY:
            return httpx.Response(200, json={"issuer": discovery_issuer, "jwks_uri": KC_JWKS})
        if str(request.url) == KC_JWKS:
            return httpx.Response(200, json={"keys": [public_jwk("kc-1")]})
        return httpx.Response(404)

    return httpx.MockTransport(handle)


def kc_token(realm_roles: list[str], **claims) -> str:
    now = int(time.time())
    body = {
        "iss": KC_ISSUER,
        "aud": ["llm-dev-kit", "account"],
        "sub": "kc-user",
        "iat": now,
        "exp": now + 300,
        "realm_access": {"roles": realm_roles},
        **claims,
    }
    return sign(body, "kc-1")


def oidc(transport: httpx.MockTransport, **kwargs) -> OidcAuthProvider:
    return OidcAuthProvider(
        issuer=KC_ISSUER,
        audience="llm-dev-kit",
        discovery_url=KC_DISCOVERY,
        transport=transport,
        **kwargs,
    )


def test_oidc_maps_realm_roles() -> None:
    provider = oidc(keycloak())
    principal = run(provider.authenticate(kc_token(["offline_access", "admin"])))
    assert principal.subject == "kc-user"
    assert principal.roles == {"admin"}
    assert principal.scopes == {"chat", "ingest", "admin"}


def test_oidc_falls_back_to_the_default_role() -> None:
    token = kc_token(["default-roles-llm-dev-kit"])
    assert run(oidc(keycloak()).authenticate(token)).scopes == {"chat"}
    assert run(oidc(keycloak(), default_role=None).authenticate(token)).scopes == frozenset()


def test_oidc_refuses_a_discovery_document_for_another_issuer() -> None:
    error = rejected(oidc(keycloak("https://evil.test")).authenticate(kc_token(["user"])))
    assert error.code is ErrorCode.UPSTREAM_UNAVAILABLE


def test_oidc_accepts_only_its_issuer(issuer: Issuer) -> None:
    provider = oidc(keycloak())
    assert provider.accepts(kc_token([]))
    assert not provider.accepts(issuer.token())
    assert not provider.accepts("sk-ldk-x")


# ------------------------------------------------------------- Authenticator


def test_no_credential_is_401_with_a_challenge(issuer: Issuer) -> None:
    error = rejected(issuer.authenticator().authenticate(None))
    assert error.code is ErrorCode.UNAUTHORIZED
    assert error.headers["WWW-Authenticate"].startswith("Bearer")


def test_other_schemes_and_unknown_bearers_are_401(issuer: Issuer) -> None:
    authenticator = issuer.authenticator()
    for header in ("Basic dXNlcjpwYXNz", "Bearer sk-local-placeholder", "Bearer "):
        assert rejected(authenticator.authenticate(header)).code is ErrorCode.UNAUTHORIZED


def test_the_first_accepting_provider_decides(issuer: Issuer) -> None:
    authenticator = Authenticator([oidc(keycloak()), issuer.provider()])
    assert run(authenticator.authenticate(f"Bearer {kc_token(['user'])}")).subject == "kc-user"
    assert run(authenticator.authenticate(f"Bearer {issuer.token()}")).subject == "user-1"


def test_legacy_anonymous_lets_old_callers_through(issuer: Issuer) -> None:
    authenticator = issuer.authenticator(allow_anonymous=True)
    assert run(authenticator.authenticate(None)) is ANONYMOUS
    # A pre-v2 cloud key is not an identity: still anonymous.
    assert run(authenticator.authenticate("Bearer sk-openai-real-key")) is ANONYMOUS
    # But a credential that claims to be an identity must be valid.
    expired = issuer.token(expires_in=-120)
    assert rejected(authenticator.authenticate(f"Bearer {expired}")).code is ErrorCode.UNAUTHORIZED


def test_require_scope(issuer: Issuer) -> None:
    viewer = run(issuer.provider().authenticate(issuer.token("viewer")))
    assert require_scope(viewer, "chat") is viewer
    with pytest.raises(ServiceError) as caught:
        require_scope(viewer, "ingest")
    assert caught.value.code is ErrorCode.FORBIDDEN


# ---------------------------------------------------------------- registry


def test_both_plugins_build_from_validated_config() -> None:
    registry = PluginRegistry()
    registry.register(local_plugin)
    registry.register(oidc_plugin)
    registry.configure(
        PluginKind.AUTH,
        "local",
        {"jwks_url": "http://w/j", "token_url": "http://w/t", "issuer": "i", "audience": "a"},
    )
    registry.configure(PluginKind.AUTH, "oidc", {"issuer": "http://kc", "audience": "a"})
    assert registry.get(AUTH, "local").name == "local"
    assert registry.get(AUTH, "oidc").name == "oidc"
    run(registry.aclose())


# ------------------------------------------------ concurrent first use (single flight)


class GatedTransport(httpx.AsyncBaseTransport):
    """The issuer's endpoints, holding every request until ``gate`` opens.

    The plain mock answers without ever yielding, so concurrent callers would
    never overlap. Holding requests makes them overlap for certain.
    """

    def __init__(self, issuer: Issuer) -> None:
        self.gate = asyncio.Event()
        self.requests = 0
        self._inner = httpx.MockTransport(issuer.handle)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await self.gate.wait()
        self.requests += 1
        return await self._inner.handle_async_request(request)


def gated_provider(issuer: Issuer) -> tuple[LocalAuthProvider, GatedTransport]:
    transport = GatedTransport(issuer)
    provider = LocalAuthProvider(
        jwks_url=JWKS_URL,
        token_url=TOKEN_URL,
        issuer=ISSUER,
        audience=AUDIENCE,
        transport=transport,
    )
    return provider, transport


async def all_at_once(provider: LocalAuthProvider, transport: GatedTransport, credential: str):
    calls = [asyncio.create_task(provider.authenticate(credential)) for _ in range(50)]
    for _ in range(20):  # let every call reach the fetch (or the shared wait for it)
        await asyncio.sleep(0)
    transport.gate.set()
    return await asyncio.gather(*calls, return_exceptions=True)


def test_fifty_concurrent_first_verifications_fetch_the_keys_once(issuer: Issuer) -> None:
    provider, transport = gated_provider(issuer)
    results = run(all_at_once(provider, transport, issuer.token(sub="alice")))
    assert all(r.subject == "alice" for r in results)
    assert issuer.jwks_fetches == 1


def test_fifty_concurrent_first_uses_of_an_api_key_exchange_it_once(issuer: Issuer) -> None:
    issuer.api_keys["sk-ldk-concurrent1"] = "user"
    provider, transport = gated_provider(issuer)
    results = run(all_at_once(provider, transport, "sk-ldk-concurrent1"))
    assert all(r.kind == "api_key" for r in results)
    assert issuer.exchanges == 1
    assert issuer.jwks_fetches == 1


def test_a_failed_shared_fetch_fails_its_callers_once_then_the_next_call_retries(
    issuer: Issuer,
) -> None:
    provider, transport = gated_provider(issuer)
    token = issuer.token(sub="alice")
    issuer.down = True

    async def scenario():
        failed = await all_at_once(provider, transport, token)
        issuer.down = False
        recovered = await provider.authenticate(token)
        return failed, recovered

    failed, recovered = run(scenario())
    assert all(
        isinstance(r, ServiceError) and r.code is ErrorCode.UPSTREAM_UNAVAILABLE for r in failed
    )
    assert recovered.subject == "alice"
    # One shared attempt failed for all fifty callers, then one retry succeeded.
    assert transport.requests == 2
