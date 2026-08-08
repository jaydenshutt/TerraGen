"""Input validation for TerraGen configurations."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import List

from terragen.config import (
    ENVIRONMENTS,
    LAYOUTS,
    NAT_MODES,
    SUPPORTED_BLUEPRINTS,
    SUPPORTED_CLOUDS,
    TerraGenConfig,
)
from terragen.regions import is_known_region


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            msg = "Configuration validation failed:\n  - " + "\n  - ".join(self.errors)
            raise ValueError(msg)


PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _suggest_project_slug(raw: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", (raw or "my-project").lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "my-project"
    if not s[0].isalpha():
        s = "p-" + s
    if len(s) < 3:
        s = (s + "-app")[:40]
    if not s[-1].isalnum():
        s = s.rstrip("-") + "x"
    return s[:40]


def validate_config(cfg: TerraGenConfig) -> ValidationResult:
    result = ValidationResult()

    if cfg.cloud not in SUPPORTED_CLOUDS:
        result.errors.append(
            f"Unsupported cloud '{cfg.cloud}'. Choose one of: {', '.join(SUPPORTED_CLOUDS)}"
        )

    if cfg.blueprint not in SUPPORTED_BLUEPRINTS:
        result.errors.append(
            f"Unknown blueprint '{cfg.blueprint}'. "
            f"Choose one of: {', '.join(SUPPORTED_BLUEPRINTS)}"
        )
    else:
        # Cloud-specific blueprint guidance
        cloud_locked = {
            "eks-ready": "aws",
            "gke-ready": "gcp",
            "aks-ready": "azure",
        }
        need = cloud_locked.get(cfg.blueprint)
        if need and cfg.cloud != need:
            result.warnings.append(
                f"Blueprint '{cfg.blueprint}' is optimized for {need.upper()}; "
                f"you selected {cfg.cloud.upper()}. Generation continues with best-effort defaults."
            )

    if cfg.nat_mode not in NAT_MODES:
        result.errors.append(
            f"Invalid nat_mode '{cfg.nat_mode}'. Choose one of: {', '.join(NAT_MODES)}"
        )

    if cfg.layout not in LAYOUTS:
        result.errors.append(
            f"Invalid layout '{cfg.layout}'. Choose one of: {', '.join(LAYOUTS)}"
        )

    if cfg.environment not in ENVIRONMENTS:
        result.warnings.append(
            f"Uncommon environment '{cfg.environment}'. "
            f"Common values: {', '.join(ENVIRONMENTS)}"
        )

    if not PROJECT_RE.match(cfg.project):
        result.errors.append(
            f"Project name '{cfg.project}' is invalid. "
            f"Try something like '{_suggest_project_slug(cfg.project)}' "
            "(3–40 chars: lowercase letters, digits, hyphens; start with a letter)."
        )

    if not cfg.region or not str(cfg.region).strip():
        result.errors.append("Region/location is required")
    elif cfg.cloud in SUPPORTED_CLOUDS and not is_known_region(cfg.cloud, cfg.region):
        result.warnings.append(
            f"Region '{cfg.region}' is not in TerraGen's curated list for {cfg.cloud}. "
            "It may still be valid — double-check the cloud console."
        )

    try:
        net = ipaddress.ip_network(cfg.vpc_cidr, strict=False)
        if net.version != 4:
            result.errors.append("Only IPv4 vpc_cidr is supported")
        if net.prefixlen > 24:
            result.warnings.append(
                f"VPC CIDR {cfg.vpc_cidr} is small (/{net.prefixlen}); "
                "consider /16–/20 for multi-AZ production."
            )
        if net.is_multicast or net.is_loopback:
            result.errors.append(f"VPC CIDR {cfg.vpc_cidr} is not a usable private range")
    except ValueError as e:
        result.errors.append(f"Invalid vpc_cidr: {e}")

    if cfg.az_count < 1 or cfg.az_count > 6:
        result.errors.append("az_count must be between 1 and 6")
    if cfg.az_count == 1 and cfg.blueprint in ("network-ha", "network-secure"):
        result.warnings.append(
            "HA/secure blueprints recommend az_count >= 2 for multi-AZ resilience"
        )

    if cfg.create_public_subnets:
        if len(cfg.public_subnets) != cfg.az_count:
            result.errors.append(
                f"public_subnets length ({len(cfg.public_subnets)}) must equal az_count ({cfg.az_count})"
            )
    elif cfg.public_subnets:
        result.warnings.append(
            "create_public_subnets is false but public_subnets were provided; they will be ignored"
        )
    if len(cfg.private_subnets) != cfg.az_count:
        result.errors.append(
            f"private_subnets length ({len(cfg.private_subnets)}) must equal az_count ({cfg.az_count})"
        )
    if cfg.enable_isolated_subnets and len(cfg.isolated_subnets) != cfg.az_count:
        result.errors.append(
            f"isolated_subnets length ({len(cfg.isolated_subnets)}) must equal az_count ({cfg.az_count})"
        )

    if cfg.nat_mode == "none" and cfg.cloud == "aws" and not cfg.enable_interface_endpoints:
        result.warnings.append(
            "nat_mode=none without interface endpoints: private instances may lack "
            "API access. Enable enable_interface_endpoints (auto-on for private-only)."
        )

    if cfg.nat_mode != "none" and not cfg.create_public_subnets:
        result.errors.append(
            "NAT requires public subnets (create_public_subnets=true) to host NAT gateways"
        )

    for email in cfg.alert_emails:
        if not EMAIL_RE.match(email):
            result.errors.append(f"Invalid alert email: {email}")

    if cfg.enable_billing_alerts and not cfg.alert_emails:
        result.warnings.append(
            "Billing alerts enabled but no alert_emails set — SNS/email subscriptions will be empty"
        )

    if cfg.enable_bastion_sg:
        for c in cfg.ssh_cidrs:
            try:
                ipaddress.ip_network(c, strict=False)
            except ValueError:
                result.errors.append(f"Invalid SSH CIDR: {c}")
        if "0.0.0.0/0" in cfg.ssh_cidrs:
            result.warnings.append(
                "Bastion/SSH security group allows 0.0.0.0/0 — avoid in production"
            )

    if cfg.cloud == "gcp" and not cfg.gcp_project_id:
        result.warnings.append(
            "GCP: gcp_project_id not set; using project name as GCP project ID. "
            "Set gcp_project_id to your real billing project."
        )

    if cfg.cloud == "azure":
        acct = cfg.azure_storage_account
        if len(acct) < 3 or len(acct) > 24 or not acct.isalnum():
            result.errors.append(
                f"Derived Azure storage account name '{acct}' is invalid. "
                "Adjust project/environment to produce a 3–24 alphanumeric name."
            )

    if cfg.nat_mode == "per_az" and cfg.az_count >= 3:
        est = cfg.cost_estimate()
        result.warnings.append(
            f"per_az NAT with {cfg.az_count} AZs ≈ ${est['monthly_usd_low']}/mo idle "
            f"(up to ~${est['monthly_usd_high']}/mo with sample egress). "
            "Consider nat_mode=single for non-prod."
        )

    return result
