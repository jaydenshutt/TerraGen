"""
Single gate: every shipped answers example loads, validates, renders,
and (when terraform/tofu is available) passes terraform validate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terragen.config import TerraGenConfig
from terragen.render import render_project
from terragen.validate import validate_config

from tests.tf_helpers import (
    terraform_binary,
    terraform_validate,
    workdir_for_config,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _answer_example_names() -> list[str]:
    names = sorted(
        p.name
        for p in EXAMPLES.iterdir()
        if p.is_file()
        and p.name.startswith("answers-")
        and p.suffix in (".yaml", ".yml", ".json")
    )
    assert names, f"No answers-* examples under {EXAMPLES}"
    return names


ANSWER_EXAMPLES = _answer_example_names()


@pytest.mark.parametrize("name", ANSWER_EXAMPLES)
def test_every_example_loads_validates_and_renders(tmp_path, name: str):
    """All shipped answers files must be valid and render without Jinja errors."""
    path = EXAMPLES / name
    assert path.exists(), path
    cfg = TerraGenConfig.from_file(path)
    result = validate_config(cfg)
    assert result.ok, f"{name}: {result.errors}"

    out = tmp_path / name.replace(".", "_")
    render_project(cfg, out, force=True)

    if cfg.is_modular:
        assert (out / "modules" / "network").is_dir()
        for env in cfg.env_list:
            assert (out / "envs" / env / "main.tf").exists(), env
    else:
        assert (out / "main.tf").exists() or (
            cfg.enable_hub_spoke and (out / "hub_spoke.tf").exists()
        )
        assert (out / "terraform.tf").exists()

    assert (out / "terragen.answers.yaml").exists()
    assert (out / ".terragen-generated").exists()

    if cfg.enable_cluster:
        if cfg.is_modular:
            cluster = out / "modules" / "cluster" / "main.tf"
            assert cluster.exists(), f"{name}: expected modules/cluster/main.tf"
            assert not (out / "modules" / "network" / "cluster.tf").exists()
        else:
            cluster = out / "cluster.tf"
            assert cluster.exists(), f"{name}: expected cluster.tf"
    if cfg.enable_hub_spoke:
        hub = (
            out / "hub_spoke.tf"
            if not cfg.is_modular
            else out / "modules" / "network" / "hub_spoke.tf"
        )
        assert hub.exists(), f"{name}: expected hub_spoke.tf"


@pytest.mark.terraform
@pytest.mark.parametrize("name", ANSWER_EXAMPLES)
def test_every_example_terraform_validate(tmp_path, name: str):
    """
    Every answers example must pass terraform init -backend=false + validate.

    Skips when terraform/tofu is not installed. CI installs terraform so this runs.
    """
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")

    path = EXAMPLES / name
    cfg = TerraGenConfig.from_file(path)
    assert validate_config(cfg).ok, validate_config(cfg).errors

    out = tmp_path / f"tf-{name.replace('.', '_')}"
    render_project(cfg, out, force=True)
    # Bootstrap validated once via modular/secure examples if present; skip by
    # default here to keep the matrix fast (still validates the main stack).
    terraform_validate(out, workdir=workdir_for_config(out, cfg), also_bootstrap=False)


@pytest.mark.terraform
def test_bootstrap_stack_terraform_validate_once(tmp_path):
    """At least one generated bootstrap/ stack must terraform-validate."""
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")

    path = EXAMPLES / "answers-aws.yaml"
    cfg = TerraGenConfig.from_file(path)
    out = tmp_path / "boot-check"
    render_project(cfg, out, force=True)
    assert (out / "bootstrap" / "main.tf").exists()
    terraform_validate(out, workdir=workdir_for_config(out, cfg), also_bootstrap=True)


@pytest.mark.terraform
def test_inventory_import_terraform_validate(tmp_path):
    """Brownfield inventory sample must produce terraform-valid HCL."""
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")

    from terragen.import_brownfield import generate_import_project, load_inventory

    inv = EXAMPLES / "inventory-aws-sample.json"
    disc = load_inventory(inv)
    out = tmp_path / "imported"
    generate_import_project(disc, out)
    assert (out / "imports.tf").exists()
    terraform_validate(out, also_bootstrap=False)
