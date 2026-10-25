"""Importing the LiteLLM plugin must use its bundled model catalog by default."""

import os
import subprocess
import sys
from pathlib import Path


def test_plugin_import_uses_local_cost_map_without_network() -> None:
    """Set LiteLLM's offline default before import and avoid a catalog fetch."""
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    source_paths = [
        project_root / "services/core/src",
        project_root / "services/plugins/litellm/src",
    ]
    inherited_pythonpath = env.get("PYTHONPATH")
    pythonpath = [str(path) for path in source_paths]
    if inherited_pythonpath:
        pythonpath.append(inherited_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    script = """
import httpx
import os

requests = []

def reject_request(*args, **kwargs):
    requests.append((args, kwargs))
    raise AssertionError("unexpected HTTP request during LiteLLM import")

httpx.Client.send = reject_request
httpx.AsyncClient.send = reject_request

import ldk_plugin_litellm.provider
from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map_source_info

assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"
source = get_model_cost_map_source_info()
assert source["source"] == "local", source
assert source["url"] is None, source
assert source["is_env_forced"] is True, source
assert not requests, requests
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
