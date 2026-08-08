"""Tests for expanded blueprints and polish helpers."""

from pathlib import Path

import pytest

from terragen.blueprints import list_blueprints
from terragen.cidrs import compute_gke_secondary_ranges, compute_three_tier_cidrs
from terragen.config import SUPPORTED_BLUEPRINTS, TerraGenConfig
from terragen.render import render_project
from terragen.validate import validate_config


def test_all_blueprint_ids_registered():
    assert set(SUPPORTED_BLUEPRINTS) == {
        "network",
        "network-ha",
        "network-secure",
        "network-private",
        "network-3tier",
        "eks-ready",
        "gke-ready",
        "aks-ready",
    }


def test_list_blueprints_filter_aws():
    ids = {b["id"] for b in list_blueprints("aws")}
    assert "eks-ready" in ids
    assert "gke-ready" not in ids


def test_three_tier_cidrs():
    pub, priv, iso = compute_three_tier_cidrs("10.0.0.0/16", 2)
    assert len(pub) == len(priv) == len(iso) == 2


def test_gke_secondaries():
    pods, svcs = compute_gke_secondary_ranges("10.0.0.0/16", 2)
    assert len(pods) == 2 and len(svcs) == 2


@pytest.mark.parametrize(
    "blueprint,cloud",
    [
        ("network-private", "aws"),
        ("network-3tier", "aws"),
        ("eks-ready", "aws"),
        ("gke-ready", "gcp"),
        ("aks-ready", "azure"),
    ],
)
def test_blueprint_renders(tmp_path, blueprint, cloud):
    data = {
        "project": f"demo-{blueprint[:8]}",
        "cloud": cloud,
        "blueprint": blueprint,
        "az_count": 2,
        "region": {"aws": "us-east-1", "gcp": "us-central1", "azure": "eastus"}[cloud],
    }
    if cloud == "gcp":
        data["gcp_project_id"] = "billing-proj"
    cfg = TerraGenConfig.from_dict(data)
    assert validate_config(cfg).ok, validate_config(cfg).errors
    out = tmp_path / blueprint
    render_project(cfg, out, force=True)
    assert (out / "network.tf").exists() or (out / "modules" / "network" / "network.tf").exists()


def test_private_blueprint_no_public():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-priv-bp", "cloud": "aws", "blueprint": "network-private"}
    )
    assert cfg.create_public_subnets is False
    assert cfg.public_subnets == []
    assert cfg.enable_interface_endpoints is True


def test_3tier_has_isolated():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-tier", "cloud": "aws", "blueprint": "network-3tier"}
    )
    assert cfg.enable_isolated_subnets
    assert len(cfg.isolated_subnets) == cfg.az_count


def test_example_files(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples"
    for name in (
        "answers-3tier.yaml",
        "answers-eks-ready.yaml",
        "answers-gke-ready.yaml",
        "answers-aks-ready.yaml",
    ):
        cfg = TerraGenConfig.from_file(root / name)
        assert validate_config(cfg).ok, name
        render_project(cfg, tmp_path / name, force=True)
