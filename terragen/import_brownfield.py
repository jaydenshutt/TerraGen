"""
Brownfield import — discover existing network resources and emit Terraform
import blocks + matching resource definitions (Terraform >= 1.5).

Supports:
  - AWS live discovery via boto3 (optional dependency)
  - AWS / GCP / Azure from inventory JSON

AWS discovery (deep) covers:
  VPC, subnets, IGW, NAT + EIP, route tables + associations + routes,
  security groups (+ rules as inline blocks), network ACLs (+ entries),
  VPC endpoints (gateway + interface).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _tags_from_aws(tag_list: Optional[List[dict]]) -> Dict[str, str]:
    if not tag_list:
        return {}
    return {t["Key"]: t["Value"] for t in tag_list if "Key" in t and "Value" in t}


def _name_from_tags(tags: Dict[str, str], fallback: str) -> str:
    return tags.get("Name") or fallback


def _tf_name(prefix: str, raw: str) -> str:
    """Sanitize a string into a valid Terraform resource name."""
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.lower()).strip("_")
    if not s:
        s = "res"
    if s[0].isdigit():
        s = f"n_{s}"
    # keep readable but unique-ish
    base = f"{prefix}_{s}"[:50]
    return base


def _hcl_str(value: str) -> str:
    return json.dumps(value)


def _hcl_map(tags: Dict[str, str], indent: int = 2) -> str:
    if not tags:
        return "{}"
    pad = " " * indent
    inner = "\n".join(f'{pad}  {_hcl_str(k)} = {_hcl_str(v)}' for k, v in sorted(tags.items()))
    return "{\n" + inner + "\n" + pad + "}"


def _hcl_list(values: List[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(_hcl_str(v) for v in values) + "]"


@dataclass
class DiscoveredNetwork:
    cloud: str
    region: str
    vpc_id: str
    vpc_cidr: str
    # VPC details
    enable_dns_support: bool = True
    enable_dns_hostnames: bool = True
    ipv6_cidr: Optional[str] = None
    # Collections of resource dicts (normalized)
    subnets: List[Dict[str, Any]] = field(default_factory=list)
    internet_gateways: List[Dict[str, Any]] = field(default_factory=list)
    nat_gateways: List[Dict[str, Any]] = field(default_factory=list)
    eips: List[Dict[str, Any]] = field(default_factory=list)
    route_tables: List[Dict[str, Any]] = field(default_factory=list)
    route_table_associations: List[Dict[str, Any]] = field(default_factory=list)
    security_groups: List[Dict[str, Any]] = field(default_factory=list)
    network_acls: List[Dict[str, Any]] = field(default_factory=list)
    vpc_endpoints: List[Dict[str, Any]] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    # Legacy / simple fields kept for backward-compatible inventories
    internet_gateway_id: Optional[str] = None
    nat_gateway_ids: List[str] = field(default_factory=list)
    route_table_ids: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_counts(self) -> Dict[str, int]:
        return {
            "subnets": len(self.subnets),
            "internet_gateways": len(self.internet_gateways)
            + (1 if self.internet_gateway_id and not self.internet_gateways else 0),
            "nat_gateways": len(self.nat_gateways) or len(self.nat_gateway_ids),
            "eips": len(self.eips),
            "route_tables": len(self.route_tables) or len(self.route_table_ids),
            "route_table_associations": len(self.route_table_associations),
            "security_groups": len(self.security_groups),
            "network_acls": len(self.network_acls),
            "vpc_endpoints": len(self.vpc_endpoints),
        }


def discover_aws_vpc(vpc_id: str, region: str) -> DiscoveredNetwork:
    """Deep-discover an AWS VPC and related network resources via boto3."""
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
    tags = _tags_from_aws(vpc.get("Tags"))
    # DNS attributes require dedicated API calls
    try:
        dns_support = ec2.describe_vpc_attribute(
            VpcId=vpc_id, Attribute="enableDnsSupport"
        )["EnableDnsSupport"]["Value"]
    except Exception:
        dns_support = True
    try:
        dns_hostnames = ec2.describe_vpc_attribute(
            VpcId=vpc_id, Attribute="enableDnsHostnames"
        )["EnableDnsHostnames"]["Value"]
    except Exception:
        dns_hostnames = False
    ipv6 = None
    for a in vpc.get("Ipv6CidrBlockAssociationSet") or []:
        state = (a.get("Ipv6CidrBlockState") or {}).get("State")
        if state in (None, "associated"):
            ipv6 = a.get("Ipv6CidrBlock")
            break

    # --- Subnets ---
    subnets: List[Dict[str, Any]] = []
    for s in ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])[
        "Subnets"
    ]:
        st = _tags_from_aws(s.get("Tags"))
        subnets.append(
            {
                "id": s["SubnetId"],
                "cidr": s["CidrBlock"],
                "az": s["AvailabilityZone"],
                "az_id": s.get("AvailabilityZoneId"),
                "public": bool(s.get("MapPublicIpOnLaunch")),
                "name": _name_from_tags(st, s["SubnetId"]),
                "tags": st,
                "assign_ipv6": bool(s.get("AssignIpv6AddressOnCreation")),
                "ipv6_cidr": (s.get("Ipv6CidrBlockAssociationSet") or [{}])[0].get(
                    "Ipv6CidrBlock"
                )
                if s.get("Ipv6CidrBlockAssociationSet")
                else None,
            }
        )

    # --- IGW ---
    internet_gateways: List[Dict[str, Any]] = []
    for g in ec2.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )["InternetGateways"]:
        gt = _tags_from_aws(g.get("Tags"))
        internet_gateways.append(
            {
                "id": g["InternetGatewayId"],
                "name": _name_from_tags(gt, g["InternetGatewayId"]),
                "tags": gt,
            }
        )

    # --- NAT + EIP ---
    nat_gateways: List[Dict[str, Any]] = []
    eips: List[Dict[str, Any]] = []
    eip_seen = set()
    for n in ec2.describe_nat_gateways(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "state", "Values": ["available", "pending"]},
        ]
    )["NatGateways"]:
        if n.get("State") not in ("available", "pending"):
            continue
        nt = _tags_from_aws(n.get("Tags"))
        addr = (n.get("NatGatewayAddresses") or [{}])[0]
        allocation_id = addr.get("AllocationId")
        nat_gateways.append(
            {
                "id": n["NatGatewayId"],
                "subnet_id": n.get("SubnetId"),
                "allocation_id": allocation_id,
                "public_ip": addr.get("PublicIp"),
                "name": _name_from_tags(nt, n["NatGatewayId"]),
                "tags": nt,
            }
        )
        if allocation_id and allocation_id not in eip_seen:
            eip_seen.add(allocation_id)
            eips.append(
                {
                    "id": allocation_id,
                    "public_ip": addr.get("PublicIp"),
                    "domain": "vpc",
                    "name": f"eip-for-{n['NatGatewayId']}",
                    "tags": {},
                }
            )

    # Fill EIP tags if possible
    if eip_seen:
        try:
            for addr in ec2.describe_addresses(AllocationIds=list(eip_seen))["Addresses"]:
                for e in eips:
                    if e["id"] == addr.get("AllocationId"):
                        e["tags"] = _tags_from_aws(addr.get("Tags"))
                        e["name"] = _name_from_tags(e["tags"], e["id"])
                        e["public_ip"] = addr.get("PublicIp") or e.get("public_ip")
        except Exception:
            pass

    # --- Route tables ---
    route_tables: List[Dict[str, Any]] = []
    route_table_associations: List[Dict[str, Any]] = []
    for rt in ec2.describe_route_tables(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["RouteTables"]:
        rtt = _tags_from_aws(rt.get("Tags"))
        routes = []
        for r in rt.get("Routes") or []:
            # skip local / incomplete
            if r.get("Origin") == "EnableVgwRoutePropagation" and r.get("State") != "active":
                continue
            routes.append(
                {
                    "destination_cidr": r.get("DestinationCidrBlock"),
                    "destination_ipv6_cidr": r.get("DestinationIpv6CidrBlock"),
                    "gateway_id": r.get("GatewayId"),
                    "nat_gateway_id": r.get("NatGatewayId"),
                    "transit_gateway_id": r.get("TransitGatewayId"),
                    "vpc_peering_id": r.get("VpcPeeringConnectionId"),
                    "egress_only_gateway_id": r.get("EgressOnlyInternetGatewayId"),
                    "network_interface_id": r.get("NetworkInterfaceId"),
                    "state": r.get("State"),
                    "origin": r.get("Origin"),
                }
            )
        main = False
        for a in rt.get("Associations") or []:
            if a.get("Main"):
                main = True
            if a.get("SubnetId"):
                route_table_associations.append(
                    {
                        "id": a.get("RouteTableAssociationId"),
                        "subnet_id": a["SubnetId"],
                        "route_table_id": rt["RouteTableId"],
                    }
                )
        route_tables.append(
            {
                "id": rt["RouteTableId"],
                "name": _name_from_tags(rtt, rt["RouteTableId"]),
                "main": main,
                "routes": routes,
                "tags": rtt,
            }
        )

    # --- Security groups ---
    security_groups: List[Dict[str, Any]] = []
    for sg in ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["SecurityGroups"]:
        sgt = _tags_from_aws(sg.get("Tags"))
        security_groups.append(
            {
                "id": sg["GroupId"],
                "name": sg.get("GroupName") or sg["GroupId"],
                "description": sg.get("Description") or "imported",
                "tags": sgt,
                "ingress": [_normalize_sg_perm(p) for p in sg.get("IpPermissions") or []],
                "egress": [
                    _normalize_sg_perm(p) for p in sg.get("IpPermissionsEgress") or []
                ],
            }
        )

    # --- Network ACLs ---
    network_acls: List[Dict[str, Any]] = []
    for nacl in ec2.describe_network_acls(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["NetworkAcls"]:
        nt = _tags_from_aws(nacl.get("Tags"))
        entries = []
        for e in nacl.get("Entries") or []:
            entries.append(
                {
                    "rule_no": e.get("RuleNumber"),
                    "egress": bool(e.get("Egress")),
                    "protocol": str(e.get("Protocol", "-1")),
                    "rule_action": e.get("RuleAction"),
                    "cidr": e.get("CidrBlock"),
                    "ipv6_cidr": e.get("Ipv6CidrBlock"),
                    "from_port": (e.get("PortRange") or {}).get("From"),
                    "to_port": (e.get("PortRange") or {}).get("To"),
                    "icmp_type": (e.get("IcmpTypeCode") or {}).get("Type"),
                    "icmp_code": (e.get("IcmpTypeCode") or {}).get("Code"),
                }
            )
        subnet_ids = [
            a["SubnetId"] for a in nacl.get("Associations") or [] if a.get("SubnetId")
        ]
        network_acls.append(
            {
                "id": nacl["NetworkAclId"],
                "name": _name_from_tags(nt, nacl["NetworkAclId"]),
                "default": bool(nacl.get("IsDefault")),
                "entries": entries,
                "subnet_ids": subnet_ids,
                "tags": nt,
            }
        )

    # --- VPC endpoints ---
    vpc_endpoints: List[Dict[str, Any]] = []
    for ep in ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["VpcEndpoints"]:
        et = _tags_from_aws(ep.get("Tags"))
        vpc_endpoints.append(
            {
                "id": ep["VpcEndpointId"],
                "service_name": ep.get("ServiceName"),
                "type": ep.get("VpcEndpointType"),  # Gateway | Interface | GatewayLoadBalancer
                "route_table_ids": ep.get("RouteTableIds") or [],
                "subnet_ids": ep.get("SubnetIds") or [],
                "security_group_ids": [
                    g.get("GroupId") for g in ep.get("Groups") or [] if g.get("GroupId")
                ],
                "private_dns_enabled": ep.get("PrivateDnsEnabled"),
                "name": _name_from_tags(et, ep["VpcEndpointId"]),
                "tags": et,
            }
        )

    return DiscoveredNetwork(
        cloud="aws",
        region=region,
        vpc_id=vpc_id,
        vpc_cidr=vpc["CidrBlock"],
        enable_dns_support=bool(dns_support),
        enable_dns_hostnames=bool(dns_hostnames),
        ipv6_cidr=ipv6,
        subnets=subnets,
        internet_gateways=internet_gateways,
        nat_gateways=nat_gateways,
        eips=eips,
        route_tables=route_tables,
        route_table_associations=route_table_associations,
        security_groups=security_groups,
        network_acls=network_acls,
        vpc_endpoints=vpc_endpoints,
        tags=tags,
        internet_gateway_id=internet_gateways[0]["id"] if internet_gateways else None,
        nat_gateway_ids=[n["id"] for n in nat_gateways],
        route_table_ids=[r["id"] for r in route_tables],
        raw={"vpc_id": vpc_id},
    )


def _normalize_sg_perm(p: dict) -> dict:
    return {
        "from_port": p.get("FromPort"),
        "to_port": p.get("ToPort"),
        "protocol": p.get("IpProtocol", "-1"),
        "cidr_blocks": [x.get("CidrIp") for x in p.get("IpRanges") or [] if x.get("CidrIp")],
        "ipv6_cidr_blocks": [
            x.get("CidrIpv6") for x in p.get("Ipv6Ranges") or [] if x.get("CidrIpv6")
        ],
        "prefix_list_ids": [
            x.get("PrefixListId") for x in p.get("PrefixListIds") or [] if x.get("PrefixListId")
        ],
        "security_groups": [
            x.get("GroupId") for x in p.get("UserIdGroupPairs") or [] if x.get("GroupId")
        ],
        "description": next(
            (
                x.get("Description")
                for x in (p.get("IpRanges") or []) + (p.get("Ipv6Ranges") or [])
                if x.get("Description")
            ),
            None,
        ),
    }


def load_inventory(path: Path) -> DiscoveredNetwork:
    """Load inventory JSON (legacy simple or deep schema)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cloud = data.get("cloud", "aws")
    vpc_id = data.get("vpc_id") or data.get("vnet_id") or ""
    vpc_cidr = data.get("vpc_cidr") or data.get("address_space") or "10.0.0.0/16"

    # Normalize IGW
    igws = list(data.get("internet_gateways") or [])
    if not igws and data.get("internet_gateway_id"):
        igws = [{"id": data["internet_gateway_id"], "name": "igw", "tags": {}}]

    # Normalize NAT
    nats = list(data.get("nat_gateways") or [])
    if not nats:
        for i, nid in enumerate(data.get("nat_gateway_ids") or []):
            nats.append(
                {
                    "id": nid,
                    "subnet_id": data.get("nat_subnet_ids", [None] * (i + 1))[i]
                    if isinstance(data.get("nat_subnet_ids"), list)
                    else None,
                    "allocation_id": (data.get("nat_allocation_ids") or [None] * (i + 1))[i]
                    if isinstance(data.get("nat_allocation_ids"), list)
                    else None,
                    "name": nid,
                    "tags": {},
                }
            )

    eips = list(data.get("eips") or [])
    for n in nats:
        if n.get("allocation_id") and not any(e.get("id") == n["allocation_id"] for e in eips):
            eips.append(
                {
                    "id": n["allocation_id"],
                    "public_ip": n.get("public_ip"),
                    "domain": "vpc",
                    "name": n["allocation_id"],
                    "tags": {},
                }
            )

    rts = list(data.get("route_tables") or [])
    if not rts:
        for rid in data.get("route_table_ids") or []:
            rts.append({"id": rid, "name": rid, "main": False, "routes": [], "tags": {}})

    # Subnets: ensure tags/name
    subnets = []
    for s in data.get("subnets") or []:
        s = dict(s)
        s.setdefault("tags", {})
        s.setdefault("name", s.get("id", "subnet"))
        s.setdefault("public", False)
        subnets.append(s)

    return DiscoveredNetwork(
        cloud=cloud,
        region=data.get("region", ""),
        vpc_id=vpc_id,
        vpc_cidr=vpc_cidr,
        enable_dns_support=data.get("enable_dns_support", True),
        enable_dns_hostnames=data.get("enable_dns_hostnames", True),
        ipv6_cidr=data.get("ipv6_cidr"),
        subnets=subnets,
        internet_gateways=igws,
        nat_gateways=nats,
        eips=eips,
        route_tables=rts,
        route_table_associations=list(data.get("route_table_associations") or []),
        security_groups=list(data.get("security_groups") or []),
        network_acls=list(data.get("network_acls") or []),
        vpc_endpoints=list(data.get("vpc_endpoints") or []),
        tags=data.get("tags") or {},
        internet_gateway_id=igws[0]["id"] if igws else data.get("internet_gateway_id"),
        nat_gateway_ids=[n["id"] for n in nats] or list(data.get("nat_gateway_ids") or []),
        route_table_ids=[r["id"] for r in rts] or list(data.get("route_table_ids") or []),
        raw=data.get("raw") or {},
    )


def generate_import_project(disc: DiscoveredNetwork, outdir: Path) -> List[Path]:
    """Write brownfield Terraform project with import blocks + resources."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    inv_path = outdir / "discovered.json"
    inv_path.write_text(json.dumps(disc.to_dict(), indent=2) + "\n", encoding="utf-8")
    written.append(inv_path)

    if disc.cloud == "aws":
        files = _aws_import_files(disc)
    elif disc.cloud in ("gcp", "azure"):
        files = _generic_import_readme(disc, disc.cloud.upper())
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
                "counts": disc.summary_counts(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(marker)
    return written


# ---------------------------------------------------------------------------
# AWS HCL generation
# ---------------------------------------------------------------------------


def _aws_import_files(disc: DiscoveredNetwork) -> Dict[str, str]:
    imports: List[str] = []
    blocks: Dict[str, List[str]] = {
        "vpc": [],
        "subnets": [],
        "gateways": [],
        "routes": [],
        "security": [],
        "acls": [],
        "endpoints": [],
        "outputs": [],
    }

    # Unique name tracking
    used_names: set = set()

    def uniq(name: str) -> str:
        base = name
        i = 2
        while name in used_names:
            name = f"{base}_{i}"
            i += 1
        used_names.add(name)
        return name

    # --- VPC ---
    imports.append(
        f'import {{\n  to = aws_vpc.main\n  id = {_hcl_str(disc.vpc_id)}\n}}\n'
    )
    dns_h = "true" if disc.enable_dns_hostnames else "false"
    dns_s = "true" if disc.enable_dns_support else "false"
    ipv6_line = ""
    if disc.ipv6_cidr:
        ipv6_line = f"\n  # IPv6 CIDR observed: {disc.ipv6_cidr} (manage assign_generated_ipv6 carefully)"
    blocks["vpc"].append(
        f'''resource "aws_vpc" "main" {{
  cidr_block           = {_hcl_str(disc.vpc_cidr)}
  enable_dns_support   = {dns_s}
  enable_dns_hostnames = {dns_h}{ipv6_line}

  tags = {_hcl_map(disc.tags or {"Name": "imported-vpc"})}
}}
'''
    )
    blocks["outputs"].append(
        'output "vpc_id" {\n  value = aws_vpc.main.id\n}\n'
    )
    blocks["outputs"].append(
        f'output "vpc_cidr" {{\n  value = aws_vpc.main.cidr_block\n}}\n'
    )

    # --- Subnets (named, not count) ---
    subnet_tf_names: Dict[str, str] = {}  # subnet_id -> tf resource name
    public_ids = []
    private_ids = []
    for s in disc.subnets:
        sid = s["id"]
        label = s.get("name") or sid
        tier = "public" if s.get("public") else "private"
        rname = uniq(_tf_name(f"subnet_{tier}", label if label != sid else sid[-8:]))
        subnet_tf_names[sid] = rname
        if s.get("public"):
            public_ids.append(sid)
        else:
            private_ids.append(sid)

        imports.append(
            f'import {{\n  to = aws_subnet.{rname}\n  id = {_hcl_str(sid)}\n}}\n'
        )
        map_pub = "true" if s.get("public") else "false"
        tags = s.get("tags") or {"Name": label, "Tier": tier}
        az = s.get("az") or "us-east-1a"
        ipv6_attr = ""
        if s.get("ipv6_cidr"):
            ipv6_attr = f"\n  # ipv6_cidr_block = {_hcl_str(s['ipv6_cidr'])}"
        blocks["subnets"].append(
            f'''resource "aws_subnet" "{rname}" {{
  vpc_id                  = aws_vpc.main.id
  cidr_block              = {_hcl_str(s["cidr"])}
  availability_zone       = {_hcl_str(az)}
  map_public_ip_on_launch = {map_pub}{ipv6_attr}

  tags = {_hcl_map(tags)}
}}
'''
        )

    if subnet_tf_names:
        blocks["outputs"].append(
            "output \"subnet_ids\" {\n  value = {\n"
            + "\n".join(
                f'    {_hcl_str(sid)} = aws_subnet.{name}.id'
                for sid, name in subnet_tf_names.items()
            )
            + "\n  }\n}\n"
        )

    # --- IGW ---
    igw_tf: Dict[str, str] = {}
    for g in disc.internet_gateways:
        rname = uniq(_tf_name("igw", g.get("name") or g["id"][-8:]))
        igw_tf[g["id"]] = rname
        imports.append(
            f'import {{\n  to = aws_internet_gateway.{rname}\n  id = {_hcl_str(g["id"])}\n}}\n'
        )
        blocks["gateways"].append(
            f'''resource "aws_internet_gateway" "{rname}" {{
  vpc_id = aws_vpc.main.id
  tags   = {_hcl_map(g.get("tags") or {"Name": g.get("name") or "imported-igw"})}
}}
'''
        )

    # --- EIP ---
    eip_tf: Dict[str, str] = {}
    for e in disc.eips:
        if not e.get("id"):
            continue
        rname = uniq(_tf_name("eip", e.get("name") or e["id"][-8:]))
        eip_tf[e["id"]] = rname
        imports.append(
            f'import {{\n  to = aws_eip.{rname}\n  id = {_hcl_str(e["id"])}\n}}\n'
        )
        blocks["gateways"].append(
            f'''resource "aws_eip" "{rname}" {{
  domain = "vpc"
  tags   = {_hcl_map(e.get("tags") or {"Name": e.get("name") or "imported-eip"})}
}}
'''
        )

    # --- NAT ---
    nat_tf: Dict[str, str] = {}
    for n in disc.nat_gateways:
        rname = uniq(_tf_name("nat", n.get("name") or n["id"][-8:]))
        nat_tf[n["id"]] = rname
        imports.append(
            f'import {{\n  to = aws_nat_gateway.{rname}\n  id = {_hcl_str(n["id"])}\n}}\n'
        )
        subnet_id = n.get("subnet_id")
        alloc = n.get("allocation_id")
        # Prefer references when we have TF names
        if subnet_id and subnet_id in subnet_tf_names:
            subnet_ref = f"aws_subnet.{subnet_tf_names[subnet_id]}.id"
        else:
            subnet_ref = _hcl_str(subnet_id or "subnet-UNKNOWN")
        if alloc and alloc in eip_tf:
            alloc_ref = f"aws_eip.{eip_tf[alloc]}.id"
        else:
            alloc_ref = _hcl_str(alloc or "eipalloc-UNKNOWN")
        depends = []
        if igw_tf:
            depends.append(f"aws_internet_gateway.{next(iter(igw_tf.values()))}")
        dep_block = ""
        if depends:
            dep_block = "\n  depends_on = [" + ", ".join(depends) + "]"
        blocks["gateways"].append(
            f'''resource "aws_nat_gateway" "{rname}" {{
  allocation_id = {alloc_ref}
  subnet_id     = {subnet_ref}{dep_block}

  tags = {_hcl_map(n.get("tags") or {"Name": n.get("name") or "imported-nat"})}
}}
'''
        )

    # --- Route tables ---
    rt_tf: Dict[str, str] = {}
    for rt in disc.route_tables:
        rname = uniq(_tf_name("rt", rt.get("name") or rt["id"][-8:]))
        rt_tf[rt["id"]] = rname
        imports.append(
            f'import {{\n  to = aws_route_table.{rname}\n  id = {_hcl_str(rt["id"])}\n}}\n'
        )
        # Build route blocks — skip local and blackhole
        route_chunks = []
        for r in rt.get("routes") or []:
            if r.get("state") and r.get("state") != "active":
                continue
            dest = r.get("destination_cidr")
            dest6 = r.get("destination_ipv6_cidr")
            if not dest and not dest6:
                continue
            # local gateway is "local" — Terraform manages local route implicitly
            if r.get("gateway_id") == "local":
                continue
            lines = []
            if dest:
                lines.append(f"    cidr_block = {_hcl_str(dest)}")
            if dest6:
                lines.append(f"    ipv6_cidr_block = {_hcl_str(dest6)}")
            # target
            if r.get("gateway_id") and str(r["gateway_id"]).startswith("igw-"):
                gid = r["gateway_id"]
                if gid in igw_tf:
                    lines.append(f"    gateway_id = aws_internet_gateway.{igw_tf[gid]}.id")
                else:
                    lines.append(f"    gateway_id = {_hcl_str(gid)}")
            elif r.get("nat_gateway_id"):
                nid = r["nat_gateway_id"]
                if nid in nat_tf:
                    lines.append(f"    nat_gateway_id = aws_nat_gateway.{nat_tf[nid]}.id")
                else:
                    lines.append(f"    nat_gateway_id = {_hcl_str(nid)}")
            elif r.get("egress_only_gateway_id"):
                lines.append(
                    f"    egress_only_gateway_id = {_hcl_str(r['egress_only_gateway_id'])}"
                )
            elif r.get("transit_gateway_id"):
                lines.append(f"    transit_gateway_id = {_hcl_str(r['transit_gateway_id'])}")
            elif r.get("vpc_peering_id"):
                lines.append(
                    f"    vpc_peering_connection_id = {_hcl_str(r['vpc_peering_id'])}"
                )
            elif r.get("gateway_id") and str(r["gateway_id"]).startswith("vpce-"):
                lines.append(f"    gateway_id = {_hcl_str(r['gateway_id'])}")
            elif r.get("network_interface_id"):
                lines.append(
                    f"    network_interface_id = {_hcl_str(r['network_interface_id'])}"
                )
            else:
                # unknown target — skip to avoid invalid HCL
                continue
            route_chunks.append("  route {\n" + "\n".join(lines) + "\n  }")

        routes_hcl = ("\n" + "\n".join(route_chunks) + "\n") if route_chunks else "\n"
        blocks["routes"].append(
            f'''resource "aws_route_table" "{rname}" {{
  vpc_id = aws_vpc.main.id
{routes_hcl}
  tags = {_hcl_map(rt.get("tags") or {"Name": rt.get("name") or "imported-rt"})}
}}
'''
        )

    # --- Associations ---
    for i, a in enumerate(disc.route_table_associations):
        sid = a.get("subnet_id")
        rid = a.get("route_table_id")
        if not sid or not rid:
            continue
        rname = uniq(_tf_name("rta", f"{sid[-6:]}_{rid[-6:]}"))
        # Import ID: subnet-id (AWS provider accepts subnet id for association)
        imports.append(
            f'import {{\n  to = aws_route_table_association.{rname}\n  id = {_hcl_str(sid)}\n}}\n'
        )
        if sid in subnet_tf_names:
            sref = f"aws_subnet.{subnet_tf_names[sid]}.id"
        else:
            sref = _hcl_str(sid)
        if rid in rt_tf:
            rref = f"aws_route_table.{rt_tf[rid]}.id"
        else:
            rref = _hcl_str(rid)
        blocks["routes"].append(
            f'''resource "aws_route_table_association" "{rname}" {{
  subnet_id      = {sref}
  route_table_id = {rref}
}}
'''
        )

    # --- Security groups ---
    sg_tf: Dict[str, str] = {}
    for sg in disc.security_groups:
        # Skip default SG name conflict carefully — still import
        rname = uniq(_tf_name("sg", sg.get("name") or sg["id"][-8:]))
        sg_tf[sg["id"]] = rname
        imports.append(
            f'import {{\n  to = aws_security_group.{rname}\n  id = {_hcl_str(sg["id"])}\n}}\n'
        )
        ingress_hcl = _sg_rules_hcl(sg.get("ingress") or [], "ingress", sg_tf)
        egress_hcl = _sg_rules_hcl(sg.get("egress") or [], "egress", sg_tf)
        # Prefer revoke rules via lifecycle if self-referential complexity is high
        lifecycle = ""
        if any(
            sg["id"] in (p.get("security_groups") or [])
            for p in (sg.get("ingress") or []) + (sg.get("egress") or [])
        ):
            lifecycle = """
  lifecycle {
    # Self-referential rules often need hand-tuning after first plan
    ignore_changes = [ingress, egress]
  }
"""
        blocks["security"].append(
            f'''resource "aws_security_group" "{rname}" {{
  name        = {_hcl_str(sg.get("name") or rname)}
  description = {_hcl_str(sg.get("description") or "imported")}
  vpc_id      = aws_vpc.main.id
{ingress_hcl}{egress_hcl}{lifecycle}
  tags = {_hcl_map(sg.get("tags") or {"Name": sg.get("name") or "imported-sg"})}
}}
'''
        )

    if sg_tf:
        blocks["outputs"].append(
            "output \"security_group_ids\" {\n  value = {\n"
            + "\n".join(f'    {_hcl_str(i)} = aws_security_group.{n}.id' for i, n in sg_tf.items())
            + "\n  }\n}\n"
        )

    # --- Network ACLs ---
    for nacl in disc.network_acls:
        rname = uniq(_tf_name("nacl", nacl.get("name") or nacl["id"][-8:]))
        imports.append(
            f'import {{\n  to = aws_network_acl.{rname}\n  id = {_hcl_str(nacl["id"])}\n}}\n'
        )
        # Inline entries as ingress/egress blocks
        ingress_parts = []
        egress_parts = []
        for e in nacl.get("entries") or []:
            if e.get("rule_no") in (None, 32767):
                # skip max/default deny often auto-managed — still include non-32767
                if e.get("rule_no") == 32767:
                    continue
            chunk = _nacl_entry_hcl(e)
            if not chunk:
                continue
            if e.get("egress"):
                egress_parts.append(chunk)
            else:
                ingress_parts.append(chunk)
        # Subnet associations via subnet_ids argument
        assoc_subnets = nacl.get("subnet_ids") or []
        subnet_ids_hcl = []
        for sid in assoc_subnets:
            if sid in subnet_tf_names:
                subnet_ids_hcl.append(f"aws_subnet.{subnet_tf_names[sid]}.id")
            else:
                subnet_ids_hcl.append(_hcl_str(sid))
        subnet_line = ""
        if subnet_ids_hcl:
            subnet_line = "\n  subnet_ids = [" + ", ".join(subnet_ids_hcl) + "]"
        blocks["acls"].append(
            f'''resource "aws_network_acl" "{rname}" {{
  vpc_id = aws_vpc.main.id{subnet_line}
{"".join(ingress_parts)}{"".join(egress_parts)}
  tags = {_hcl_map(nacl.get("tags") or {"Name": nacl.get("name") or "imported-nacl"})}

  lifecycle {{
    # Default NACL associations are sensitive — review before apply
    ignore_changes = [subnet_ids]
  }}
}}
'''
        )

    # --- VPC endpoints ---
    for ep in disc.vpc_endpoints:
        rname = uniq(_tf_name("vpce", ep.get("name") or ep["id"][-8:]))
        imports.append(
            f'import {{\n  to = aws_vpc_endpoint.{rname}\n  id = {_hcl_str(ep["id"])}\n}}\n'
        )
        etype = ep.get("type") or "Gateway"
        svc = ep.get("service_name") or "com.amazonaws.region.service"
        extra = ""
        if etype == "Gateway":
            rt_ids = ep.get("route_table_ids") or []
            refs = []
            for rid in rt_ids:
                if rid in rt_tf:
                    refs.append(f"aws_route_table.{rt_tf[rid]}.id")
                else:
                    refs.append(_hcl_str(rid))
            if refs:
                extra += "\n  route_table_ids = [" + ", ".join(refs) + "]"
        else:
            sn_refs = []
            for sid in ep.get("subnet_ids") or []:
                if sid in subnet_tf_names:
                    sn_refs.append(f"aws_subnet.{subnet_tf_names[sid]}.id")
                else:
                    sn_refs.append(_hcl_str(sid))
            if sn_refs:
                extra += "\n  subnet_ids = [" + ", ".join(sn_refs) + "]"
            sg_refs = []
            for gid in ep.get("security_group_ids") or []:
                if gid in sg_tf:
                    sg_refs.append(f"aws_security_group.{sg_tf[gid]}.id")
                else:
                    sg_refs.append(_hcl_str(gid))
            if sg_refs:
                extra += "\n  security_group_ids = [" + ", ".join(sg_refs) + "]"
            if ep.get("private_dns_enabled") is not None:
                extra += (
                    f"\n  private_dns_enabled = "
                    f'{"true" if ep.get("private_dns_enabled") else "false"}'
                )
        blocks["endpoints"].append(
            f'''resource "aws_vpc_endpoint" "{rname}" {{
  vpc_id            = aws_vpc.main.id
  service_name      = {_hcl_str(svc)}
  vpc_endpoint_type = {_hcl_str(etype)}{extra}

  tags = {_hcl_map(ep.get("tags") or {"Name": ep.get("name") or "imported-vpce"})}
}}
'''
        )

    region = disc.region or "us-east-1"
    versions = f'''terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = {_hcl_str(region)}
}}
'''

    counts = disc.summary_counts()
    readme = f'''# Brownfield import — `{disc.vpc_id}`

Generated by **TerraGen** deep AWS network discovery.

## What was imported

| Resource | Count |
|----------|------:|
| VPC | 1 |
| Subnets | {counts["subnets"]} |
| Internet gateways | {counts["internet_gateways"]} |
| NAT gateways | {counts["nat_gateways"]} |
| Elastic IPs | {counts["eips"]} |
| Route tables | {counts["route_tables"]} |
| RT associations | {counts["route_table_associations"]} |
| Security groups | {counts["security_groups"]} |
| Network ACLs | {counts["network_acls"]} |
| VPC endpoints | {counts["vpc_endpoints"]} |

Region: `{region}` · CIDR: `{disc.vpc_cidr}`

## Files

| File | Contents |
|------|----------|
| `imports.tf` | Terraform 1.5+ `import` blocks |
| `vpc.tf` | VPC |
| `subnets.tf` | Subnets (named resources) |
| `gateways.tf` | IGW, EIP, NAT |
| `routes.tf` | Route tables + associations |
| `security.tf` | Security groups |
| `acls.tf` | Network ACLs |
| `endpoints.tf` | VPC endpoints |
| `outputs.tf` | Useful IDs |
| `discovered.json` | Full inventory snapshot |

## Steps

```bash
terraform init
terraform plan     # expect near-empty plan after attribute alignment
# Edit any remaining drift (tags, SG self-refs, NACL defaults)
terraform apply    # applies import blocks into state
```

## Safety

- **Do not** run `terraform destroy` on production until you understand blast radius.
- Security groups with **self-references** may use `ignore_changes` on rules — refine manually.
- Default NACL `subnet_ids` may be ignored for safety — verify associations.
- After adoption, prefer normal Terraform workflows (PRs, plan, apply).

## Re-run discovery

```bash
terragen import --cloud aws --vpc-id {disc.vpc_id} --region {region} --out .
# or refresh inventory only:
# terragen import --cloud aws --vpc-id {disc.vpc_id} --region {region} --dry-run > discovered.json
```
'''

    files: Dict[str, str] = {
        "versions.tf": versions,
        "imports.tf": "\n".join(imports) + "\n",
        "vpc.tf": "\n".join(blocks["vpc"]) + "\n",
        "subnets.tf": "\n".join(blocks["subnets"]) + "\n" if blocks["subnets"] else "",
        "gateways.tf": "\n".join(blocks["gateways"]) + "\n" if blocks["gateways"] else "",
        "routes.tf": "\n".join(blocks["routes"]) + "\n" if blocks["routes"] else "",
        "security.tf": "\n".join(blocks["security"]) + "\n" if blocks["security"] else "",
        "acls.tf": "\n".join(blocks["acls"]) + "\n" if blocks["acls"] else "",
        "endpoints.tf": "\n".join(blocks["endpoints"]) + "\n"
        if blocks["endpoints"]
        else "",
        "outputs.tf": "\n".join(blocks["outputs"]) + "\n",
        "README.md": readme,
        ".gitignore": "**/.terraform/*\n*.tfstate\n*.tfstate.*\n*.tfplan\n",
    }
    # Drop empty optional files
    return {k: v for k, v in files.items() if v.strip()}


def _sg_rules_hcl(perms: List[dict], kind: str, sg_tf: Dict[str, str]) -> str:
    parts = []
    for p in perms:
        lines = []
        proto = p.get("protocol") if p.get("protocol") is not None else "-1"
        lines.append(f"    protocol  = {_hcl_str(str(proto))}")
        # AWS uses null ports for all protocols (-1)
        fp = p.get("from_port")
        tp = p.get("to_port")
        if fp is not None:
            lines.append(f"    from_port = {int(fp)}")
        else:
            lines.append("    from_port = 0")
        if tp is not None:
            lines.append(f"    to_port   = {int(tp)}")
        else:
            lines.append("    to_port   = 0")
        cidrs = p.get("cidr_blocks") or []
        if cidrs:
            lines.append(f"    cidr_blocks = {_hcl_list(cidrs)}")
        v6 = p.get("ipv6_cidr_blocks") or []
        if v6:
            lines.append(f"    ipv6_cidr_blocks = {_hcl_list(v6)}")
        pls = p.get("prefix_list_ids") or []
        if pls:
            lines.append(f"    prefix_list_ids = {_hcl_list(pls)}")
        sgs = p.get("security_groups") or []
        if sgs:
            # Use IDs as strings — cross-SG refs after import are safer as IDs
            lines.append(f"    security_groups = {_hcl_list(sgs)}")
        if p.get("description"):
            lines.append(f"    description = {_hcl_str(p['description'])}")
        # Skip empty rules with no destinations
        if not cidrs and not v6 and not pls and not sgs:
            continue
        parts.append(f"  {kind} {{\n" + "\n".join(lines) + "\n  }\n")
    return "\n" + "".join(parts) if parts else ""


def _nacl_entry_hcl(e: dict) -> str:
    rule_no = e.get("rule_no")
    if rule_no is None:
        return ""
    action = e.get("rule_action") or "deny"
    proto = str(e.get("protocol") if e.get("protocol") is not None else "-1")
    kind = "egress" if e.get("egress") else "ingress"
    # AWS provider requires from_port/to_port even for protocol -1 (use 0)
    fp = e.get("from_port")
    tp = e.get("to_port")
    if fp is None:
        fp = 0
    if tp is None:
        tp = 0
    lines = [
        f"    rule_no    = {int(rule_no)}",
        f"    protocol   = {_hcl_str(proto)}",
        f"    action     = {_hcl_str(action)}",
        f"    from_port  = {int(fp)}",
        f"    to_port    = {int(tp)}",
    ]
    if e.get("cidr"):
        lines.append(f"    cidr_block = {_hcl_str(e['cidr'])}")
    if e.get("ipv6_cidr"):
        lines.append(f"    ipv6_cidr_block = {_hcl_str(e['ipv6_cidr'])}")
    if e.get("icmp_type") is not None:
        lines.append(f"    icmp_type  = {int(e['icmp_type'])}")
    if e.get("icmp_code") is not None:
        lines.append(f"    icmp_code  = {int(e['icmp_code'])}")
    return f"  {kind} {{\n" + "\n".join(lines) + "\n  }\n"


def _generic_import_readme(disc: DiscoveredNetwork, label: str) -> Dict[str, str]:
    readme = f'''# Brownfield import — {label}

VPC/VNet ID: `{disc.vpc_id}`
CIDR: `{disc.vpc_cidr}`

Live auto-discovery for {label} is inventory-driven. Provide a full
`discovered.json` (export from your cloud tools) and re-run:

```bash
terragen import --inventory discovered.json --out ./imported
```

For **AWS live discovery** (deep):

```bash
pip install boto3
terragen import --cloud aws --vpc-id vpc-xxxxxxxx --region us-east-1 --out ./imported
```

That path discovers subnets, IGW, NAT/EIP, route tables, SGs, NACLs, and endpoints.
'''
    return {
        "README.md": readme,
        "discovered.json": json.dumps(disc.to_dict(), indent=2) + "\n",
    }
