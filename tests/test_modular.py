"""Tests for modular layout, private-only, doctor, schema, bootstrap dry-run."""

from pathlib import Path

import pytest

from terragen.cli import main
from terragen.config import TerraGenConfig
from terragen.doctor import run_doctor
from terragen.render import render_project
from terragen.schema import answers_schema, write_schema
from terragen.validate import validate_config


def test_modular_layout_structure(tmp_path):
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-mod",
            "cloud": "aws",
            "layout": "modular",
            "environments": ["dev", "prod"],
            "blueprint": "network",
            "az_count": 2,
        }
    )
    assert cfg.is_modular
    assert cfg.env_list == ["dev", "prod"]
    out = tmp_path / "mod"
    result = render_project(cfg, out, force=True)
    assert (out / "modules" / "network" / "network.tf").exists()
    assert (out / "envs" / "dev" / "main.tf").exists()
    assert (out / "envs" / "prod" / "main.tf").exists()
    assert (out / "envs" / "dev" / "backend.tf").exists()
    main_tf = (out / "envs" / "dev" / "main.tf").read_text()
    assert 'source = "../../modules/network"' in main_tf
    assert "module " in main_tf
    assert any("oidc" in f for f in result.relative_files)


def test_private_only_aws(tmp_path):
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-priv",
            "cloud": "aws",
            "private_only": True,
            "az_count": 2,
        }
    )
    assert cfg.nat_mode == "none"
    assert cfg.create_public_subnets is False
    assert cfg.enable_interface_endpoints is True
    assert cfg.public_subnets == []
    assert len(cfg.private_subnets) == 2
    assert validate_config(cfg).ok

    out = tmp_path / "priv"
    render_project(cfg, out, force=True)
    net = (out / "network.tf").read_text()
    assert "aws_vpc_endpoint" in net
    assert "interface" in net
    assert "enable_if_eps" in net or "interface_endpoints" in net


def test_doctor_ok():
    report = run_doctor()
    assert report.ok
    names = [c.name for c in report.checks]
    assert "terragen" in names
    assert "templates" in names


def test_schema_write(tmp_path):
    path = write_schema(tmp_path / "answers.schema.json")
    assert path.exists()
    schema = answers_schema()
    assert schema["properties"]["layout"]["enum"] == ["flat", "modular"]


def test_schema_covers_v3_fields():
    """JSON Schema should document cluster / hub-spoke / IPv6 answers keys."""
    props = answers_schema()["properties"]
    for key in (
        "enable_ipv6",
        "enable_cluster",
        "cluster_name",
        "cluster_version",
        "node_desired_size",
        "node_min_size",
        "node_max_size",
        "enable_hub_spoke",
        "spoke_count",
        "hub_cidr",
        "hub_spoke_connectivity",
        "isolated_subnets",
        "enable_isolated_subnets",
        "private_only",
    ):
        assert key in props, f"missing schema property: {key}"


def test_cli_schema(capsys):
    assert main(["schema"]) == 0
    assert "TerraGen Answers" in capsys.readouterr().out


def test_cli_doctor():
    assert main(["doctor"]) == 0


def test_cli_bootstrap_dry_run(tmp_path):
    out = tmp_path / "boot"
    # generate first
    assert (
        main(
            [
                "generate",
                "--non-interactive",
                "--project",
                "boot-demo",
                "--cloud",
                "aws",
                "--out",
                str(out),
                "--force",
            ]
        )
        == 0
    )
    assert (out / "bootstrap" / "main.tf").exists()
    rc = main(["bootstrap", "--project-dir", str(out), "--dry-run"])
    assert rc == 0


def test_example_modular_and_private(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples"
    for name in ("answers-modular.yaml", "answers-private-only.yaml"):
        cfg = TerraGenConfig.from_file(root / name)
        assert validate_config(cfg).ok, name
        render_project(cfg, tmp_path / name, force=True)
