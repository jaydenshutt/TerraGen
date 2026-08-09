"""Deep brownfield import tests."""

from pathlib import Path

from terragen.import_brownfield import (
    DiscoveredNetwork,
    generate_import_project,
    load_inventory,
)


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_load_deep_inventory():
    disc = load_inventory(EXAMPLES / "inventory-aws-sample.json")
    assert disc.cloud == "aws"
    assert disc.vpc_id.startswith("vpc-")
    assert len(disc.subnets) == 4
    assert len(disc.internet_gateways) == 1
    assert len(disc.nat_gateways) == 1
    assert len(disc.eips) == 1
    assert len(disc.route_tables) == 2
    assert len(disc.route_table_associations) == 4
    assert len(disc.security_groups) == 2
    assert len(disc.network_acls) == 1
    assert len(disc.vpc_endpoints) == 1
    counts = disc.summary_counts()
    assert counts["subnets"] == 4
    assert counts["security_groups"] == 2


def test_generate_deep_project_files(tmp_path):
    disc = load_inventory(EXAMPLES / "inventory-aws-sample.json")
    out = tmp_path / "imported"
    files = generate_import_project(disc, out)

    assert (out / "imports.tf").exists()
    assert (out / "vpc.tf").exists()
    assert (out / "subnets.tf").exists()
    assert (out / "gateways.tf").exists()
    assert (out / "routes.tf").exists()
    assert (out / "security.tf").exists()
    assert (out / "acls.tf").exists()
    assert (out / "endpoints.tf").exists()
    assert (out / "outputs.tf").exists()
    assert (out / "discovered.json").exists()
    assert (out / "README.md").exists()

    imports = (out / "imports.tf").read_text()
    assert "aws_vpc.main" in imports
    assert "aws_subnet." in imports
    assert "aws_internet_gateway." in imports
    assert "aws_nat_gateway." in imports
    assert "aws_eip." in imports
    assert "aws_route_table." in imports
    assert "aws_route_table_association." in imports
    assert "aws_security_group." in imports
    assert "aws_network_acl." in imports
    assert "aws_vpc_endpoint." in imports

    vpc = (out / "vpc.tf").read_text()
    assert 'cidr_block           = "10.0.0.0/16"' in vpc or 'cidr_block' in vpc
    assert "enable_dns_support" in vpc

    routes = (out / "routes.tf").read_text()
    assert "aws_route_table" in routes
    assert "nat_gateway_id" in routes or "gateway_id" in routes

    security = (out / "security.tf").read_text()
    assert "ingress" in security
    assert "egress" in security

    # Named resources, not count-only subnets
    subnets = (out / "subnets.tf").read_text()
    assert "availability_zone" in subnets
    assert "map_public_ip_on_launch" in subnets

    assert len(files) >= 8


def test_legacy_inventory_still_loads(tmp_path):
    """Minimal legacy shape still works."""
    p = tmp_path / "legacy.json"
    p.write_text(
        """{
      "cloud": "aws",
      "region": "us-west-2",
      "vpc_id": "vpc-legacy",
      "vpc_cidr": "10.1.0.0/16",
      "internet_gateway_id": "igw-legacy",
      "nat_gateway_ids": ["nat-legacy"],
      "route_table_ids": ["rtb-1"],
      "subnets": [
        {"id": "subnet-1", "cidr": "10.1.0.0/24", "az": "us-west-2a", "public": true, "name": "pub"}
      ],
      "tags": {"Name": "legacy"}
    }"""
    )
    disc = load_inventory(p)
    assert disc.internet_gateways and disc.internet_gateways[0]["id"] == "igw-legacy"
    out = tmp_path / "out"
    generate_import_project(disc, out)
    assert (out / "vpc.tf").exists()
    assert "vpc-legacy" in (out / "imports.tf").read_text()


def test_cli_import_inventory(tmp_path):
    from terragen.cli import main

    out = tmp_path / "cli-imp"
    rc = main(
        [
            "import",
            "--inventory",
            str(EXAMPLES / "inventory-aws-sample.json"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert (out / "imports.tf").exists()
    assert (out / "security.tf").exists()
