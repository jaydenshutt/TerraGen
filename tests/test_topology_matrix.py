"""
Topology and layout matrix: hub-spoke modes, multi-cloud hub, modular combos.

When terraform/tofu is available, each case is terraform-validated.
Marked ``terraform`` so ``pytest -m "not terraform"`` stays offline-friendly.
"""

from __future__ import annotations

import pytest

from terragen.config import TerraGenConfig
from terragen.render import render_project
from terragen.validate import validate_config

from tests.tf_helpers import terraform_binary, terraform_validate, workdir_for_config

pytestmark = pytest.mark.terraform


def _maybe_tf_validate(cfg: TerraGenConfig, out) -> None:
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")
    # Main env only - bootstrap covered separately in test_examples
    terraform_validate(out, workdir=workdir_for_config(out, cfg), also_bootstrap=False)


# ── Hub-spoke connectivity & multi-cloud ─────────────────────────────────────


@pytest.mark.parametrize(
    "cloud,connectivity,region,extra",
    [
        ("aws", "tgw", "us-east-1", {}),
        ("aws", "peering", "us-east-1", {}),
        ("gcp", "peering", "us-central1", {"gcp_project_id": "billing-proj"}),
        ("azure", "peering", "eastus", {}),
    ],
)
def test_hub_spoke_connectivity_matrix(tmp_path, cloud, connectivity, region, extra):
    data = {
        "project": f"hub-{cloud}-{connectivity[:3]}",
        "cloud": cloud,
        "region": region,
        "blueprint": "hub-spoke",
        "hub_cidr": "10.0.0.0/16",
        "spoke_count": 2,
        "hub_spoke_connectivity": connectivity,
        "az_count": 2,
        "nat_mode": "single",
        **extra,
    }
    cfg = TerraGenConfig.from_dict(data)
    assert cfg.enable_hub_spoke
    assert validate_config(cfg).ok, validate_config(cfg).errors

    out = tmp_path / f"{cloud}-{connectivity}"
    render_project(cfg, out, force=True)
    assert (out / "main.tf").exists()
    hub_tf = (out / "hub_spoke.tf").read_text(encoding="utf-8")

    if cloud == "aws" and connectivity == "tgw":
        assert "aws_ec2_transit_gateway" in hub_tf
        assert "aws_vpc_peering_connection" not in hub_tf
    elif cloud == "aws" and connectivity == "peering":
        assert "aws_vpc_peering_connection" in hub_tf
        assert "aws_ec2_transit_gateway" not in hub_tf
    elif cloud == "gcp":
        assert "google_compute_network_peering" in hub_tf
    elif cloud == "azure":
        assert "azurerm_virtual_network_peering" in hub_tf

    _maybe_tf_validate(cfg, out)


# ── Modular + cluster / hub ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "blueprint,cloud,region,extra",
    [
        ("eks-cluster", "aws", "us-east-1", {}),
        ("gke-cluster", "gcp", "us-central1", {"gcp_project_id": "billing-proj"}),
        ("aks-cluster", "azure", "eastus", {}),
        (
            "hub-spoke",
            "aws",
            "us-east-1",
            {
                "hub_cidr": "10.20.0.0/16",
                "spoke_count": 2,
                "hub_spoke_connectivity": "peering",
            },
        ),
    ],
)
def test_modular_with_cluster_or_hub(tmp_path, blueprint, cloud, region, extra):
    data = {
        "project": f"mod-{blueprint[:8].replace('-', '')}",
        "cloud": cloud,
        "region": region,
        "blueprint": blueprint,
        "layout": "modular",
        "environments": ["dev", "prod"],
        "az_count": 2,
        **extra,
    }
    cfg = TerraGenConfig.from_dict(data)
    assert cfg.is_modular
    assert validate_config(cfg).ok, validate_config(cfg).errors

    out = tmp_path / f"mod-{blueprint}"
    render_project(cfg, out, force=True)

    mod = out / "modules" / "network"
    assert (mod / "main.tf").exists()
    assert (out / "envs" / "dev" / "main.tf").exists()
    assert (out / "envs" / "prod" / "main.tf").exists()

    if cfg.enable_cluster:
        cmod = out / "modules" / "cluster"
        assert cmod.is_dir()
        assert (cmod / "main.tf").exists()
        assert (cmod / "variables.tf").exists()
        assert (cmod / "terraform.tf").exists()
        # Cluster must NOT live inside the network module
        assert not (mod / "cluster.tf").exists()
        main = (out / "envs" / "dev" / "main.tf").read_text(encoding="utf-8")
        assert 'module "cluster"' in main
        assert 'module "network"' in main
        assert "module.network" in main or "module.network." in main
    if cfg.enable_hub_spoke:
        assert (mod / "hub_spoke.tf").exists()
        main = (out / "envs" / "dev" / "main.tf").read_text(encoding="utf-8")
        assert "enable_hub_spoke" in main

    _maybe_tf_validate(cfg, out)


# ── Flat cluster blueprints (terraform gate) ──────────────────────────────────


@pytest.mark.parametrize(
    "blueprint,cloud,region,extra",
    [
        ("eks-cluster", "aws", "us-east-1", {}),
        ("gke-cluster", "gcp", "us-central1", {"gcp_project_id": "billing-proj"}),
        ("aks-cluster", "azure", "eastus", {}),
    ],
)
def test_flat_cluster_terraform_validate(tmp_path, blueprint, cloud, region, extra):
    data = {
        "project": f"flat-{blueprint[:8].replace('-', '')}",
        "cloud": cloud,
        "region": region,
        "blueprint": blueprint,
        "layout": "flat",
        "az_count": 2,
        **extra,
    }
    cfg = TerraGenConfig.from_dict(data)
    assert validate_config(cfg).ok, validate_config(cfg).errors
    out = tmp_path / blueprint
    render_project(cfg, out, force=True)
    assert (out / "cluster.tf").exists()
    _maybe_tf_validate(cfg, out)
