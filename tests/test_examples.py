"""Ensure shipped example answer files load and render."""

from pathlib import Path

import pytest

from terragen.config import TerraGenConfig
from terragen.render import render_project
from terragen.validate import validate_config

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize(
    "name",
    [
        "answers-aws.yaml",
        "answers-aws-secure.yaml",
        "answers-gcp.yaml",
        "answers-azure.yaml",
        "answers-aws.json",
    ],
)
def test_example_renders(tmp_path, name):
    path = EXAMPLES / name
    assert path.exists(), path
    cfg = TerraGenConfig.from_file(path)
    result = validate_config(cfg)
    # examples should be valid (warnings ok)
    assert result.ok, result.errors
    out = tmp_path / name
    render_project(cfg, out, force=True)
    assert (out / "network.tf").exists()
