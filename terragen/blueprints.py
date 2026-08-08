"""Blueprint catalog and descriptions."""

from __future__ import annotations

from typing import Dict, List

BLUEPRINTS: Dict[str, dict] = {
    "network": {
        "name": "Network Foundation",
        "summary": "Production-ready VPC/VNet with public & private subnets, IGW, and optional NAT.",
        "includes": [
            "Multi-AZ public and private subnets",
            "Internet gateway / equivalent",
            "Optional NAT (none / single / per-AZ)",
            "Baseline security groups / firewalls / NSGs",
            "Remote state, CI, and policy stubs",
        ],
        "best_for": "Greenfield apps, sandboxes, standard three-tier web apps",
        "clouds": ["aws", "gcp", "azure"],
    },
    "network-ha": {
        "name": "High Availability Network",
        "summary": "Multi-AZ resilient network with per-AZ NAT, flow logs, and gateway endpoints.",
        "includes": [
            "Everything in Network Foundation",
            "Per-AZ NAT gateways",
            "VPC/VNet flow logs",
            "Gateway endpoints for object storage",
            "Minimum 2 AZs",
        ],
        "best_for": "Staging and production that need AZ independence",
        "clouds": ["aws", "gcp", "azure"],
    },
    "network-secure": {
        "name": "Secure Network",
        "summary": "HA network plus threat detection, tighter defaults, and observability hooks.",
        "includes": [
            "Everything in High Availability Network",
            "AWS GuardDuty (AWS)",
            "Restrictive SSH defaults",
            "Billing alert scaffolding when emails provided",
            "Policy-as-code starters",
        ],
        "best_for": "Production and regulated workloads",
        "clouds": ["aws", "gcp", "azure"],
    },
    "network-private": {
        "name": "Private-Only Network",
        "summary": "No public subnets or NAT; private connectivity via endpoints (AWS) / PGA (GCP).",
        "includes": [
            "Private subnets only",
            "No NAT idle cost",
            "AWS interface + gateway VPC endpoints pack",
            "Flow logs on",
            "Ideal for internal services and data planes",
        ],
        "best_for": "Internal platforms, batch, data processing without public edge",
        "clouds": ["aws", "gcp", "azure"],
    },
    "network-3tier": {
        "name": "Three-Tier Network",
        "summary": "Public (edge), private (app), and isolated (data) subnets per AZ.",
        "includes": [
            "Public subnets for load balancers / bastion",
            "Private app subnets with NAT for outbound",
            "Isolated data subnets with no internet route",
            "Flow logs + gateway endpoints",
            "Minimum 2 AZs",
        ],
        "best_for": "Classic web / app / database layouts with a locked-down data tier",
        "clouds": ["aws", "gcp", "azure"],
    },
    "eks-ready": {
        "name": "EKS-Ready Network (AWS)",
        "summary": "HA VPC tagged for Kubernetes, with endpoints for ECR/SSM and ELB-ready public subnets.",
        "includes": [
            "Per-AZ NAT, flow logs, gateway + interface endpoints",
            "Subnet tags: kubernetes.io/role/elb and internal-elb",
            "ECR/SSM/logs endpoints for private node pulls",
            "GuardDuty on",
            "Minimum 2 AZs",
        ],
        "best_for": "Amazon EKS clusters (network only — not the control plane)",
        "clouds": ["aws"],
    },
    "gke-ready": {
        "name": "GKE-Ready Network (GCP)",
        "summary": "Custom VPC with secondary ranges for pods/services and Cloud NAT for nodes.",
        "includes": [
            "Custom-mode VPC + private subnets with PGA",
            "Secondary IP ranges for GKE pods and services",
            "Cloud Router + Cloud NAT",
            "Flow logs",
            "Firewall baseline for internal traffic",
        ],
        "best_for": "Google Kubernetes Engine (network only — not the cluster)",
        "clouds": ["gcp"],
    },
    "aks-ready": {
        "name": "AKS-Ready Network (Azure)",
        "summary": "HA VNet with NAT, NSG defaults, and subnets sized for Azure Kubernetes Service.",
        "includes": [
            "Multi-AZ style subnet pairs with NAT Gateway",
            "NSG baselines on public/private subnets",
            "Tags for AKS ownership",
            "Flow-log scaffolding notes",
            "Minimum 2 AZs",
        ],
        "best_for": "Azure Kubernetes Service (network only — not the cluster)",
        "clouds": ["azure"],
    },
}


def list_blueprints(cloud: str | None = None) -> List[dict]:
    items = []
    for k, v in BLUEPRINTS.items():
        if cloud and cloud.lower() not in v.get("clouds", ["aws", "gcp", "azure"]):
            continue
        items.append({"id": k, **{kk: vv for kk, vv in v.items() if kk != "defaults"}})
    return items


def get_blueprint(blueprint_id: str) -> dict:
    if blueprint_id not in BLUEPRINTS:
        raise KeyError(
            f"Unknown blueprint '{blueprint_id}'. "
            f"Available: {', '.join(BLUEPRINTS)}"
        )
    return BLUEPRINTS[blueprint_id]


def describe_blueprint(blueprint_id: str) -> str:
    bp = get_blueprint(blueprint_id)
    lines = [
        f"{bp['name']} ({blueprint_id})",
        bp["summary"],
        "",
        "Includes:",
        *[f"  • {item}" for item in bp["includes"]],
        "",
        f"Best for: {bp['best_for']}",
        f"Clouds: {', '.join(bp.get('clouds', []))}",
    ]
    return "\n".join(lines)


def blueprint_ids_for_cloud(cloud: str) -> List[str]:
    return [b["id"] for b in list_blueprints(cloud)]
