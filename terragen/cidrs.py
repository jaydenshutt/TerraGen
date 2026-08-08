"""Subnet CIDR planning for multi-AZ public/private/isolated layouts."""

from __future__ import annotations

import ipaddress
from typing import List, Sequence, Tuple


def _carve(vpc_cidr: str, total_subnets: int) -> List[str]:
    if total_subnets < 1:
        raise ValueError("Need at least one subnet")
    net = ipaddress.ip_network(vpc_cidr, strict=False)
    if net.version != 4:
        raise ValueError("Only IPv4 VPC CIDRs are supported currently")
    bits = max(1, (total_subnets - 1).bit_length())
    new_prefix = net.prefixlen + bits
    if new_prefix > 28:
        new_prefix = 28
    if new_prefix > net.max_prefixlen:
        raise ValueError(
            f"VPC CIDR {vpc_cidr} is too small to create {total_subnets} subnets"
        )
    available = list(net.subnets(new_prefix=new_prefix))
    if len(available) < total_subnets:
        raise ValueError(
            f"VPC CIDR {vpc_cidr} only yields {len(available)} /{new_prefix} "
            f"subnets but {total_subnets} are required"
        )
    return [str(available[i]) for i in range(total_subnets)]


def compute_subnet_cidrs(
    vpc_cidr: str,
    az_count: int,
    *,
    public_prefix_extra: int | None = None,
    private_prefix_extra: int | None = None,
) -> Tuple[List[str], List[str]]:
    """
    Divide a VPC/VNet CIDR into public and private subnets for each AZ.

    Returns (public_cidrs, private_cidrs), each of length az_count.
    """
    if az_count < 1:
        raise ValueError("az_count must be at least 1")
    if az_count > 6:
        raise ValueError("az_count must be 6 or fewer (practical cloud AZ limit)")

    blocks = _carve(vpc_cidr, az_count * 2)
    public_cidrs: List[str] = []
    private_cidrs: List[str] = []
    for i in range(az_count):
        public_cidrs.append(blocks[i * 2])
        private_cidrs.append(blocks[i * 2 + 1])
    return public_cidrs, private_cidrs


def compute_three_tier_cidrs(
    vpc_cidr: str, az_count: int
) -> Tuple[List[str], List[str], List[str]]:
    """
    Public + private (app) + isolated (data) per AZ.

    Returns (public, private, isolated).
    """
    if az_count < 1:
        raise ValueError("az_count must be at least 1")
    if az_count > 6:
        raise ValueError("az_count must be 6 or fewer")
    blocks = _carve(vpc_cidr, az_count * 3)
    public, private, isolated = [], [], []
    for i in range(az_count):
        public.append(blocks[i * 3])
        private.append(blocks[i * 3 + 1])
        isolated.append(blocks[i * 3 + 2])
    return public, private, isolated


def compute_private_only_cidrs(vpc_cidr: str, az_count: int) -> List[str]:
    """Carve one private subnet per AZ when no public subnets are needed."""
    if az_count < 1:
        raise ValueError("az_count must be at least 1")
    return _carve(vpc_cidr, az_count)


def compute_gke_secondary_ranges(
    vpc_cidr: str, az_count: int
) -> Tuple[List[str], List[str]]:
    """
    Allocate secondary CIDRs for GKE pods/services outside the primary VPC
    by using a parallel private space derived from shifting into 172.16/12-ish
    when VPC is 10.x, otherwise nested carve from unused half.

    Simpler approach: derive from 172.16.0.0/12 slices unique per AZ.
    """
    # Fixed secondary space for GKE to avoid overlapping primary VPC commonly in 10.0.0.0/8
    base = ipaddress.ip_network("172.16.0.0/12")
    # Need 2 * az_count secondaries (pods + services)
    total = az_count * 2
    bits = max(1, (total - 1).bit_length())
    # /12 + bits → e.g. az_count=2 → 4 subnets → +2 → /14
    new_prefix = min(base.prefixlen + bits + 2, 20)  # leave room for pods
    # Prefer /18 pods and /20 services style sizes
    pod_prefix = 18
    svc_prefix = 20
    pods: List[str] = []
    services: List[str] = []
    # Carve sequential /18 then /20 from 172.16.0.0/12
    # Align cursor to network boundaries with strict=False
    cursor = int(base.network_address)
    for _ in range(az_count):
        pod_net = ipaddress.ip_network((cursor, pod_prefix), strict=False)
        # snap to actual network address
        pod_net = ipaddress.ip_network(f"{pod_net.network_address}/{pod_prefix}")
        cursor = int(pod_net.broadcast_address) + 1
        svc_net = ipaddress.ip_network((cursor, svc_prefix), strict=False)
        svc_net = ipaddress.ip_network(f"{svc_net.network_address}/{svc_prefix}")
        cursor = int(svc_net.broadcast_address) + 1
        if not pod_net.subnet_of(base) or not svc_net.subnet_of(base):
            raise ValueError("Could not allocate GKE secondary ranges in 172.16.0.0/12")
        pods.append(str(pod_net))
        services.append(str(svc_net))
    return pods, services


def validate_custom_subnets(
    vpc_cidr: str,
    public_subnets: Sequence[str],
    private_subnets: Sequence[str],
    isolated_subnets: Sequence[str] | None = None,
) -> None:
    """Ensure custom subnet CIDRs fit inside the VPC and do not overlap."""
    vpc = ipaddress.ip_network(vpc_cidr, strict=False)
    all_nets = []
    if not private_subnets:
        raise ValueError("private subnet list cannot be empty")
    for label, cidrs in (
        ("public", public_subnets or []),
        ("private", private_subnets),
        ("isolated", isolated_subnets or []),
    ):
        for c in cidrs:
            try:
                n = ipaddress.ip_network(c, strict=False)
            except ValueError as e:
                raise ValueError(f"Invalid {label} subnet CIDR '{c}': {e}") from e
            if not n.subnet_of(vpc):
                raise ValueError(f"{label} subnet {c} is not inside VPC {vpc_cidr}")
            all_nets.append(n)

    for i, a in enumerate(all_nets):
        for b in all_nets[i + 1 :]:
            if a.overlaps(b):
                raise ValueError(f"Overlapping subnets: {a} and {b}")


def summarize_address_space(
    vpc_cidr: str,
    public_subnets: Sequence[str],
    private_subnets: Sequence[str],
    isolated_subnets: Sequence[str] | None = None,
) -> dict:
    """Return a human-readable summary of the planned address space."""
    vpc = ipaddress.ip_network(vpc_cidr, strict=False)
    return {
        "vpc_cidr": str(vpc),
        "vpc_hosts_approx": vpc.num_addresses - 2 if vpc.num_addresses > 2 else 0,
        "public_subnets": list(public_subnets),
        "private_subnets": list(private_subnets),
        "isolated_subnets": list(isolated_subnets or []),
        "public_count": len(public_subnets),
        "private_count": len(private_subnets),
        "isolated_count": len(isolated_subnets or []),
    }
