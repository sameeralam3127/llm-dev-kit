"""Every proxied location in the gateway sends the client's real address.

nginx inherits server-level ``proxy_set_header`` directives only into a
location that sets none of its own. A location that sets even one (``Host``,
say) silently drops ``X-Real-IP``, so the upstream sees no client address, and
a client can supply the header itself. The web app keys its rate limits on
``X-Real-IP``, so that would let anyone pick a fresh rate-limit bucket per
request, or put every client in one shared bucket.
"""

import re
from pathlib import Path

import pytest

CONF = Path(__file__).resolve().parents[1] / "nginx" / "nginx.conf"

CLIENT_HEADERS = {
    "X-Real-IP": "$remote_addr",
    "X-Forwarded-For": "$proxy_add_x_forwarded_for",
    "X-Forwarded-Proto": "$scheme",
}


def _blocks(text: str, keyword: str) -> list[tuple[str, str]]:
    """(header, body) for each ``keyword ... { body }``, braces balanced."""
    found = []
    # The header must sit on one line with no ";": an upstream's
    # "server web:3000 resolve;" line is a directive, not a block.
    for match in re.finditer(rf"^[ \t]*{keyword}\b([^{{;\n]*)\{{", text, re.MULTILINE):
        depth, i = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        found.append((match.group(1).strip(), text[match.end() : i - 1]))
    return found


def _headers(body: str) -> dict[str, str]:
    return dict(re.findall(r"^\s*proxy_set_header\s+(\S+)\s+([^;]+);", body, re.MULTILINE))


def _proxied_locations() -> list[tuple[str, str]]:
    (_, server), *_ = _blocks(CONF.read_text(), "server")
    return [(name, body) for name, body in _blocks(server, "location") if "proxy_pass" in body]


def test_the_server_block_sets_the_client_headers() -> None:
    (_, server), *_ = _blocks(CONF.read_text(), "server")
    top_level = re.sub(r"location\b[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", server)
    assert _headers(top_level).items() >= CLIENT_HEADERS.items()


@pytest.mark.parametrize(
    "name,body",
    _proxied_locations(),
    ids=lambda v: v if v.startswith("/") or v.startswith("=") else "",
)
def test_every_proxied_location_sends_the_client_address(name: str, body: str) -> None:
    own = _headers(body)
    if not own:
        return  # inherits the server-level headers, which the test above checks
    missing = {h: v for h, v in CLIENT_HEADERS.items() if own.get(h) != v}
    assert not missing, (
        f"location {name} sets its own proxy_set_header, so nginx drops the "
        f"server-level ones; it must repeat {sorted(missing)}"
    )


def test_server_header_hides_the_nginx_version() -> None:
    conf = CONF.read_text()
    assert re.search(r"^\s*server_tokens\s+off;", conf, re.MULTILINE)
