"""Tests for clusters, hub-spoke, IPv6, and brownfield import."""

from pathlib import Path

import pytest

from terragen.cidrs import compute_spoke_cidrs
from terragen.config import SUPPORTED_BLUEPRINTS, TerraGenConfig
from terragen.import_brownfield import generate_import_project, load_inventory
from terragen.render import render_project
from terragen.validate import validate_config


def test_new_blueprints_registered():
    for bp in (
        "eks-cluster",
        "gke-cluster",
        "aks-cluster",
        "hub-spoke",
    ):
        assert bp in SUPPORTED_BLUEPRINTS


def test_spoke_cidrs():
    spokes = compute_spoke_cidrs("10.0.0.0/16", 3)
    assert len(spokes) == 3
    assert "10.0.0.0/16" not in spokes


def test_eks_cluster_config():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-eks-c", "blueprint": "eks-cluster"}
    )
    assert cfg.cloud == "aws"
    assert cfg.enable_cluster
    assert cfg.cluster_name
    assert cfg.enable_eks_subnet_tags


def test_hub_spoke_config():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-hub",
            "blueprint": "hub-spoke",
            "spoke_count": 2,
            "hub_cidr": "10.0.0.0/16",
        }
    )
    assert cfg.enable_hub_spoke
    assert len(cfg.spoke_cidrs) == 2


def test_hub_spoke_invalid_spoke_count():
    """spoke_count=0 should not crash from_dict; validate reports an error."""
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-hub-bad",
            "blueprint": "hub-spoke",
            "spoke_count": 0,
            "hub_cidr": "10.0.0.0/16",
        }
    )
    result = validate_config(cfg)
    assert not result.ok
    assert any("spoke_count" in e for e in result.errors)


def test_cluster_blueprint_resets_unknown_region():
    """eks-cluster forces AWS and replaces a GCP region with an AWS default."""
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-eks-reg",
            "cloud": "gcp",
            "region": "us-central1",
            "blueprint": "eks-cluster",
        }
    )
    assert cfg.cloud == "aws"
    assert cfg.region == "us-east-1"
    assert validate_config(cfg).ok


def test_cluster_node_size_validation():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-eks-nodes",
            "blueprint": "eks-cluster",
            "node_min_size": 3,
            "node_desired_size": 1,
            "node_max_size": 2,
        }
    )
    result = validate_config(cfg)
    assert not result.ok
    assert any("node_desired_size" in e for e in result.errors)


def test_ipv6_flag():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-v6", "cloud": "aws", "enable_ipv6": True}
    )
    assert cfg.enable_ipv6


@pytest.mark.parametrize(
    "blueprint,cloud",
    [
        ("eks-cluster", "aws"),
        ("gke-cluster", "gcp"),
        ("aks-cluster", "azure"),
        ("hub-spoke", "aws"),
    ],
)
def test_render_v3_blueprints(tmp_path, blueprint, cloud):
    data = {
        "project": f"demo-{blueprint[:10].replace('-', '')}",
        "cloud": cloud,
        "blueprint": blueprint,
        "az_count": 2,
        "region": {"aws": "us-east-1", "gcp": "us-central1", "azure": "eastus"}[cloud],
    }
    if cloud == "gcp":
        data["gcp_project_id"] = "billing-proj"
    if blueprint == "hub-spoke":
        data["spoke_count"] = 2
        data["hub_cidr"] = "10.0.0.0/16"
    cfg = TerraGenConfig.from_dict(data)
    assert validate_config(cfg).ok, validate_config(cfg).errors
    out = tmp_path / blueprint
    render_project(cfg, out, force=True)
    if cfg.enable_cluster:
        assert (out / "cluster.tf").exists()
    if cfg.enable_hub_spoke:
        assert (out / "hub_spoke.tf").exists()


def test_ipv6_render_aws(tmp_path):
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-ipv6",
            "cloud": "aws",
            "blueprint": "network",
            "enable_ipv6": True,
        }
    )
    out = tmp_path / "ipv6"
    render_project(cfg, out, force=True)
    net = (out / "main.tf").read_text()
    assert "assign_generated_ipv6_cidr_block" in net
    assert "egress_only_internet_gateway" in net


def test_brownfield_import_from_inventory(tmp_path):
    inv = Path(__file__).resolve().parents[1] / "examples" / "inventory-aws-sample.json"
    disc = load_inventory(inv)
    out = tmp_path / "imported"
    files = generate_import_project(disc, out)
    assert (out / "imports.tf").exists()
    assert (out / "main.tf").exists()
    assert "import {" in (out / "imports.tf").read_text()
    assert disc.vpc_id in (out / "imports.tf").read_text()
    assert len(files) >= 6


# Example answers files (including v3) are covered by tests/test_examples.py.
