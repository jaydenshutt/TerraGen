"""GCP / Azure inventory-based brownfield import (no live cloud accounts)."""

from pathlib import Path

import pytest

from terragen.cli import main
from terragen.import_brownfield import generate_import_project, load_inventory

from tests.tf_helpers import terraform_binary, terraform_validate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_load_gcp_inventory():
    disc = load_inventory(EXAMPLES / "inventory-gcp-sample.json")
    assert disc.cloud == "gcp"
    assert disc.project_id == "demo-billing-project"
    assert disc.network_name() == "legacy-vpc"
    assert len(disc.subnets) == 3
    assert len(disc.routers) == 1
    assert len(disc.firewalls) == 2
    assert disc.summary_counts()["firewalls"] == 2


def test_load_azure_inventory():
    disc = load_inventory(EXAMPLES / "inventory-azure-sample.json")
    assert disc.cloud == "azure"
    assert disc.resource_group == "rg-legacy-net"
    assert disc.network_name() == "vnet-legacy"
    assert len(disc.subnets) == 3
    assert len(disc.network_security_groups) == 1
    assert len(disc.public_ips) == 1
    assert len(disc.nat_gateways) == 1


def test_gcp_requires_project_id(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"cloud":"gcp","region":"us-central1","vpc_id":"net","subnets":[]}')
    with pytest.raises(ValueError, match="project_id"):
        load_inventory(p)


def test_azure_requires_resource_group(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"cloud":"azure","region":"eastus","vpc_id":"vnet-x","subnets":[]}')
    with pytest.raises(ValueError, match="resource_group"):
        load_inventory(p)


def test_generate_gcp_import_project(tmp_path):
    disc = load_inventory(EXAMPLES / "inventory-gcp-sample.json")
    out = tmp_path / "gcp-imp"
    files = generate_import_project(disc, out)
    assert (out / "imports.tf").exists()
    assert (out / "main.tf").exists()
    assert (out / "subnets.tf").exists()
    assert (out / "routers.tf").exists()
    assert (out / "firewalls.tf").exists()
    assert (out / "terraform.tf").exists()
    assert (out / "providers.tf").exists()
    assert (out / "discovered.json").exists()
    assert not (out / "network.tf").exists()
    assert not (out / "versions.tf").exists()

    imports = (out / "imports.tf").read_text(encoding="utf-8")
    assert "google_compute_network.main" in imports
    assert "google_compute_subnetwork." in imports
    assert "google_compute_router." in imports
    assert "google_compute_router_nat." in imports
    assert "google_compute_firewall." in imports
    assert "projects/demo-billing-project/global/networks/legacy-vpc" in imports

    net = (out / "main.tf").read_text(encoding="utf-8")
    assert "google_compute_network" in net
    assert "auto_create_subnetworks" in net

    sub = (out / "subnets.tf").read_text(encoding="utf-8")
    assert "secondary_ip_range" in sub
    assert "10.100.0.0/16" in sub
    assert len(files) >= 8


def test_generate_azure_import_project(tmp_path):
    disc = load_inventory(EXAMPLES / "inventory-azure-sample.json")
    out = tmp_path / "az-imp"
    generate_import_project(disc, out)
    assert (out / "imports.tf").exists()
    assert (out / "main.tf").exists()
    assert (out / "terraform.tf").exists()
    assert (out / "providers.tf").exists()
    assert (out / "subnets.tf").exists()
    assert (out / "nsg.tf").exists()
    assert (out / "routes.tf").exists()
    assert (out / "public_ips.tf").exists()
    assert (out / "nat.tf").exists()
    assert not (out / "resource_group.tf").exists()
    assert not (out / "network.tf").exists()

    main = (out / "main.tf").read_text(encoding="utf-8")
    assert "azurerm_resource_group" in main
    assert "azurerm_virtual_network" in main

    imports = (out / "imports.tf").read_text(encoding="utf-8")
    assert "azurerm_virtual_network.main" in imports
    assert "azurerm_subnet." in imports
    assert "azurerm_network_security_group." in imports
    assert "azurerm_nat_gateway." in imports

    nsg = (out / "nsg.tf").read_text(encoding="utf-8")
    assert "security_rule" in nsg
    assert "AllowHttps" in nsg


def test_cli_import_gcp_inventory(tmp_path):
    out = tmp_path / "cli-gcp"
    rc = main(
        [
            "import",
            "--inventory",
            str(EXAMPLES / "inventory-gcp-sample.json"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert (out / "main.tf").exists()
    assert "google_compute_network" in (out / "main.tf").read_text(encoding="utf-8")
    # Re-import cleans and rewrites without requiring --force for our marker
    rc2 = main(
        [
            "import",
            "--inventory",
            str(EXAMPLES / "inventory-gcp-sample.json"),
            "--out",
            str(out),
        ]
    )
    assert rc2 == 0
    assert (out / "main.tf").exists()


def test_cli_import_azure_inventory(tmp_path):
    out = tmp_path / "cli-az"
    rc = main(
        [
            "import",
            "--inventory",
            str(EXAMPLES / "inventory-azure-sample.json"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert (out / "main.tf").exists()
    assert "azurerm_virtual_network" in (out / "main.tf").read_text(encoding="utf-8")


def test_import_refuses_foreign_directory(tmp_path):
    out = tmp_path / "foreign"
    out.mkdir()
    (out / "notes.txt").write_text("user data", encoding="utf-8")
    disc = load_inventory(EXAMPLES / "inventory-aws-sample.json")
    with pytest.raises(FileExistsError):
        generate_import_project(disc, out, force=False)
    generate_import_project(disc, out, force=True)
    assert (out / "main.tf").exists()
    assert not (out / "notes.txt").exists()


@pytest.mark.terraform
@pytest.mark.parametrize(
    "inventory",
    [
        "inventory-gcp-sample.json",
        "inventory-azure-sample.json",
    ],
)
def test_multicloud_import_terraform_validate(tmp_path, inventory: str):
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")
    disc = load_inventory(EXAMPLES / inventory)
    out = tmp_path / inventory.replace(".json", "")
    generate_import_project(disc, out)
    terraform_validate(out, also_bootstrap=False)
