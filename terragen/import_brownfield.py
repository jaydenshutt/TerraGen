"""
Brownfield import — discover existing network resources and emit Terraform
import blocks + matching resource stubs.

Supports:
  - AWS via boto3 (optional) or a JSON inventory file
  - GCP / Azure via inventory JSON (CLI discovery best-effort)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DiscoveredNetwork:
    cloud: str
    region: str
    vpc_id: str
    vpc_cidr: str
    subnets: List[Dict[str, Any]] = field(default_factory=list)
    internet_gateway_id: Optional[str] = None
    nat_gateway_ids: List[str] = field(default_factory=list)
    route_table_ids: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def discover_aws_vpc(vpc_id: str, region: str) -> DiscoveredNetwork:
    """Discover an AWS VPC using boto3."""
    try:
        import boto3
    except ImportError as e:
        raise RuntimeError(
            "boto3 is required for live AWS discovery. "
            "Install with: pip install boto3  — or pass --inventory JSON instead."
        ) from e

    ec2 = boto3.client("ec2", region_name=region)
    vpcs = ec2.describe_vpcs(VpcIds=[vpc_id])["Vpcs"]
    if not vpcs:
        raise ValueError(f"VPC not found: {vpc_id}")
    vpc = vpcs[0]
    tags = {t["Key"]: t["Value"] for t in vpc.get("Tags", [])}

    subnets_resp = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]
    subnets = []
    for s in subnets_resp:
        subnets.append(
            {
                "id": s["SubnetId"],
                "cidr": s["CidrBlock"],
                "az": s["AvailabilityZone"],
                "public": s.get("MapPublicIpOnLaunch", False),
                "name": next(
                    (t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"),
                    s["SubnetId"],
                ),
            }
        )

    igws = ec2.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )["InternetGateways"]
    igw_id = igws[0]["InternetGatewayId"] if igws else None

    nats = ec2.describe_nat_gateways(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "state", "Values": ["available"]},
        ]
    )["NatGateways"]
    nat_ids = [n["NatGatewayId"] for n in nats]

    rts = ec2.describe_route_tables(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["RouteTables"]
    rt_ids = [r["RouteTableId"] for r in rts]

    return DiscoveredNetwork(
        cloud="aws",
        region=region,
        vpc_id=vpc_id,
        vpc_cidr=vpc["CidrBlock"],
        subnets=subnets,
        internet_gateway_id=igw_id,
        nat_gateway_ids=nat_ids,
        route_table_ids=rt_ids,
        tags=tags,
        raw={"vpc": vpc},
    )


def load_inventory(path: Path) -> DiscoveredNetwork:
    """Load a previously saved or hand-written inventory JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return DiscoveredNetwork(
        cloud=data["cloud"],
        region=data.get("region", ""),
        vpc_id=data["vpc_id"],
        vpc_cidr=data["vpc_cidr"],
        subnets=data.get("subnets", []),
        internet_gateway_id=data.get("internet_gateway_id"),
        nat_gateway_ids=data.get("nat_gateway_ids", []),
        route_table_ids=data.get("route_table_ids", []),
        tags=data.get("tags", {}),
        raw=data.get("raw", {}),
    )


def generate_import_project(disc: DiscoveredNetwork, outdir: Path) -> List[Path]:
    """
    Write a brownfield Terraform project with import blocks (TF >= 1.5)
    and resource stubs matching discovered network objects.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    inv_path = outdir / "discovered.json"
    inv_path.write_text(json.dumps(disc.to_dict(), indent=2) + "\n", encoding="utf-8")
    written.append(inv_path)

    if disc.cloud == "aws":
        files = _aws_import_files(disc)
    elif disc.cloud == "gcp":
        files = _generic_import_readme(disc, "GCP")
    elif disc.cloud == "azure":
        files = _generic_import_readme(disc, "Azure")
    else:
        raise ValueError(f"Unsupported cloud for import: {disc.cloud}")

    for name, content in files.items():
        path = outdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    marker = outdir / ".terragen-generated"
    marker.write_text(
        json.dumps(
            {
                "generator": "TerraGen",
                "mode": "brownfield-import",
                "cloud": disc.cloud,
                "vpc_id": disc.vpc_id,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(marker)
    return written


def _aws_import_files(disc: DiscoveredNetwork) -> Dict[str, str]:
    public = [s for s in disc.subnets if s.get("public")]
    private = [s for s in disc.subnets if not s.get("public")]
    if not private and disc.subnets:
        # fall back: first half private naming by Name tag
        private = [s for s in disc.subnets if "public" not in s.get("name", "").lower()]
        public = [s for s in disc.subnets if s not in private]

    import_lines = [
        f'import {{\n  to = aws_vpc.main\n  id = "{disc.vpc_id}"\n}}\n'
    ]
    resources = [
        f'''resource "aws_vpc" "main" {{
  cidr_block = "{disc.vpc_cidr}"
  # Review and align attributes after terraform plan
  tags = {{
    Name = "imported-vpc"
  }}
}}
'''
    ]

    for i, s in enumerate(public):
        import_lines.append(
            f'import {{\n  to = aws_subnet.public[{i}]\n  id = "{s["id"]}"\n}}\n'
        )
    if public:
        resources.append(
            f'''resource "aws_subnet" "public" {{
  count = {len(public)}

  vpc_id     = aws_vpc.main.id
  cidr_block = element({json.dumps([s["cidr"] for s in public])}, count.index)
  # availability_zone = element({json.dumps([s["az"] for s in public])}, count.index)
  tags = {{
    Name = "imported-public-${{count.index}}"
    Tier = "public"
  }}
}}
'''
        )

    for i, s in enumerate(private):
        import_lines.append(
            f'import {{\n  to = aws_subnet.private[{i}]\n  id = "{s["id"]}"\n}}\n'
        )
    if private:
        resources.append(
            f'''resource "aws_subnet" "private" {{
  count = {len(private)}

  vpc_id     = aws_vpc.main.id
  cidr_block = element({json.dumps([s["cidr"] for s in private])}, count.index)
  tags = {{
    Name = "imported-private-${{count.index}}"
    Tier = "private"
  }}
}}
'''
        )

    if disc.internet_gateway_id:
        import_lines.append(
            f'import {{\n  to = aws_internet_gateway.main[0]\n  id = "{disc.internet_gateway_id}"\n}}\n'
        )
        resources.append(
            '''resource "aws_internet_gateway" "main" {
  count  = 1
  vpc_id = aws_vpc.main.id
  tags = {
    Name = "imported-igw"
  }
}
'''
        )

    versions = '''terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "%s"
}
''' % disc.region

    readme = f'''# Brownfield import — {disc.vpc_id}

Generated by **TerraGen** from a live AWS VPC discovery.

## What this does

1. `import` blocks (Terraform ≥ 1.5) map existing IDs into state
2. Resource stubs describe the network so `terraform plan` can reconcile

## Steps

```bash
terraform init
terraform plan    # review; fix drift attributes
terraform apply   # binds state only if no changes — or adopt after edits
```

## Discovered summary

| Item | Value |
|------|--------|
| VPC | `{disc.vpc_id}` |
| CIDR | `{disc.vpc_cidr}` |
| Region | `{disc.region}` |
| Subnets | {len(disc.subnets)} |
| IGW | `{disc.internet_gateway_id or "none"}` |
| NAT GWs | {len(disc.nat_gateway_ids)} |

See `discovered.json` for the full inventory.

## Next steps

- Align tags, DNS settings, and route tables with reality
- Optionally regenerate a greenfield TerraGen stack and migrate carefully
- Do **not** `terraform destroy` this stack unless you intend to delete production networks
'''

    return {
        "versions.tf": versions,
        "imports.tf": "\n".join(import_lines) + "\n",
        "network.tf": "\n".join(resources) + "\n",
        "README.md": readme,
        ".gitignore": "**/.terraform/*\n*.tfstate\n*.tfstate.*\n",
    }


def _generic_import_readme(disc: DiscoveredNetwork, label: str) -> Dict[str, str]:
    readme = f'''# Brownfield import — {label}

VPC/VNet ID: `{disc.vpc_id}`
CIDR: `{disc.vpc_cidr}`

Live auto-discovery for {label} currently expects an inventory file:

```bash
terragen import --inventory discovered.json --out ./imported
```

Inventory JSON shape:

```json
{{
  "cloud": "{disc.cloud}",
  "region": "{disc.region}",
  "vpc_id": "{disc.vpc_id}",
  "vpc_cidr": "{disc.vpc_cidr}",
  "subnets": [
    {{"id": "...", "cidr": "10.0.1.0/24", "az": "...", "public": false, "name": "..."}}
  ]
}}
```

For AWS live discovery:

```bash
terragen import --cloud aws --vpc-id vpc-xxxxxxxx --region us-east-1 --out ./imported
```
'''
    return {
        "README.md": readme,
        "discovered.json": json.dumps(disc.to_dict(), indent=2) + "\n",
    }
