"""The Compose stack publishes exactly one port, and only on localhost by default.

Redis, Chroma and Ollama have no authentication, and the Python APIs have none
until Phase 4, so nothing but the gateway may be reachable from the host, and
the gateway itself must default to 127.0.0.1. Enforced here so it cannot
regress quietly.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = sorted(p for p in ROOT.glob("*compose*.y*ml") if p.is_file())
GATEWAY = "nginx"

# ${VAR:-default}, ${VAR-default}, ${VAR}: resolved as if VAR were unset.
_VARIABLE = re.compile(r"\$\{(\w+)(?::?-([^}]*))?\}")


def _services(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text()) or {}
    services: dict[str, dict[str, Any]] = data.get("services") or {}
    return services


def _default(value: str) -> str:
    """Substitute every ${...} with its default, as Compose does when unset."""
    return _VARIABLE.sub(lambda m: m.group(2) or "", value)


def _host_ip(port: str | int | dict[str, Any]) -> str:
    """Host interface of one `ports:` entry; "" means all interfaces."""
    if isinstance(port, dict):  # long syntax
        return _default(str(port.get("host_ip", "")))
    parts = _default(str(port)).split(":")
    # "80" / "8080:80" bind every interface; "ip:8080:80" names one.
    return parts[0] if len(parts) == 3 else ""


def test_compose_files_are_found() -> None:
    assert ROOT / "docker-compose.yml" in COMPOSE_FILES


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda p: p.name)
def test_only_the_gateway_publishes_ports(path: Path) -> None:
    publishing = {
        name: service["ports"]
        for name, service in _services(path).items()
        if service.get("ports") and name != GATEWAY
    }
    assert publishing == {}, f"{path.name}: only {GATEWAY} may publish ports"


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda p: p.name)
def test_gateway_binds_to_localhost_by_default(path: Path) -> None:
    ports = _services(path).get(GATEWAY, {}).get("ports") or []
    for port in ports:
        assert _host_ip(port) == "127.0.0.1", (
            f"{path.name}: {GATEWAY} port {port!r} must default to 127.0.0.1"
        )


def test_the_default_stack_publishes_the_gateway() -> None:
    assert _services(ROOT / "docker-compose.yml")[GATEWAY].get("ports")


def test_the_default_stack_is_not_a_dev_stack() -> None:
    """No --reload and no source bind mounts outside compose.dev.yml."""
    for name, service in _services(ROOT / "docker-compose.yml").items():
        command = service.get("command") or ""
        command = command if isinstance(command, str) else " ".join(command)
        assert "--reload" not in command, f"{name} runs with --reload"
        mounts = [v for v in service.get("volumes") or [] if isinstance(v, str)]
        sources = [m for m in mounts if m.startswith("./services/")]
        assert sources == [], f"{name} bind-mounts source: {sources}"


def test_the_dev_overlay_is_opt_in() -> None:
    # An override file would be applied by every plain `docker compose up`.
    assert not (ROOT / "docker-compose.override.yml").exists()
    assert (ROOT / "compose.dev.yml").exists()


@pytest.mark.parametrize(
    ("entry", "host_ip"),
    [
        ("${GATEWAY_BIND:-127.0.0.1}:8080:80", "127.0.0.1"),
        ("${GATEWAY_BIND}:8080:80", ""),
        ("8080:80", ""),
        ("127.0.0.1:6379:6379", "127.0.0.1"),
        (80, ""),
        ({"target": 80, "published": 8080, "host_ip": "0.0.0.0"}, "0.0.0.0"),
        ({"target": 80, "published": 8080}, ""),
    ],
)
def test_host_ip_parsing(entry: str | int | dict[str, Any], host_ip: str) -> None:
    assert _host_ip(entry) == host_ip


@pytest.mark.parametrize("service", ["llm-service", "rag-service"])
def test_services_reading_legacy_anonymous_know_the_gateway_bind(service: str) -> None:
    """They refuse ALLOW_LEGACY_ANONYMOUS off loopback, so they must see the
    same GATEWAY_BIND the gateway's port uses, default included."""
    services = _services(ROOT / "docker-compose.yml")
    environment = services[service]["environment"]
    assert "ALLOW_LEGACY_ANONYMOUS" in environment
    gateway_port = services[GATEWAY]["ports"][0]
    assert _default(environment["GATEWAY_BIND"]) == _host_ip(gateway_port) == "127.0.0.1"
