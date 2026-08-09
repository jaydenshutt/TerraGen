"""Configuration model for TerraGen generation runs."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from terragen.cidrs import (
    compute_gke_secondary_ranges,
    compute_private_only_cidrs,
    compute_subnet_cidrs,
    compute_three_tier_cidrs,
    validate_custom_subnets,
)
from terragen.regions import default_region, estimate_nat_monthly_usd, is_known_region

SUPPORTED_CLOUDS = ("aws", "gcp", "azure")
SUPPORTED_BLUEPRINTS = (
    "network",
    "network-ha",
    "network-secure",
    "network-private",
    "network-3tier",
    "eks-ready",
    "gke-ready",
    "aks-ready",
    "eks-cluster",
    "gke-cluster",
    "aks-cluster",
    "hub-spoke",
)
NAT_MODES = ("none", "single", "per_az")
ENVIRONMENTS = ("dev", "staging", "prod", "shared")
LAYOUTS = ("flat", "modular")

# Default interface endpoint services for private-only AWS networking
DEFAULT_AWS_INTERFACE_ENDPOINTS = (
    "ssm",
    "ssmmessages",
    "ec2messages",
    "ecr.api",
    "ecr.dkr",
    "logs",
    "sts",
    "kms",
    "secretsmanager",
)


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "project"


@dataclass
class TerraGenConfig:
    """Normalized configuration used for template rendering."""

    project: str = "my-cloud-project"
    cloud: str = "aws"
    region: str = "us-east-1"
    environment: str = "dev"
    blueprint: str = "network"

    vpc_cidr: str = "10.0.0.0/16"
    az_count: int = 2
    public_subnets: List[str] = field(default_factory=list)
    private_subnets: List[str] = field(default_factory=list)
    isolated_subnets: List[str] = field(default_factory=list)

    # Networking options
    nat_mode: str = "single"  # none | single | per_az
    enable_flow_logs: bool = True
    enable_vpc_endpoints: bool = False  # gateway endpoints (S3/DynamoDB)
    enable_interface_endpoints: bool = False  # AWS interface endpoints for private use
    interface_endpoints: List[str] = field(default_factory=list)
    enable_ipv6: bool = False
    create_public_subnets: bool = True  # false for private-only layouts
    enable_isolated_subnets: bool = False  # 3-tier data tier
    # Kubernetes helpers
    enable_eks_subnet_tags: bool = False
    enable_gke_secondary_ranges: bool = False
    gke_pod_cidrs: List[str] = field(default_factory=list)
    gke_service_cidrs: List[str] = field(default_factory=list)
    enable_aks_tags: bool = False

    # Real managed Kubernetes clusters (not just network prep)
    enable_cluster: bool = False
    cluster_name: str = ""
    cluster_version: str = ""  # empty = provider default / latest supported
    node_instance_type: str = "t3.medium"
    node_desired_size: int = 2
    node_min_size: int = 1
    node_max_size: int = 4
    cluster_private_endpoint: bool = True

    # Hub-and-spoke
    enable_hub_spoke: bool = False
    hub_cidr: str = "10.0.0.0/16"
    spoke_count: int = 2
    spoke_cidrs: List[str] = field(default_factory=list)
    hub_spoke_connectivity: str = "tgw"  # tgw | peering (AWS); peering for GCP/Azure

    # IPv6 dual-stack (already had enable_ipv6)
    ipv6_only: bool = False  # reserved; dual-stack is default when enable_ipv6


    # Security
    enable_bastion_sg: bool = False
    ssh_cidrs: List[str] = field(default_factory=lambda: ["10.0.0.0/8"])
    enable_guardduty: bool = False  # AWS
    enable_security_center: bool = False  # placeholder naming for multi-cloud
    enable_nsg_defaults: bool = True

    # Observability / cost
    enable_billing_alerts: bool = False
    billing_thresholds: Dict[str, float] = field(
        default_factory=lambda: {"low": 50.0, "medium": 200.0, "high": 500.0}
    )
    alert_emails: List[str] = field(default_factory=list)

    # State / packaging / layout
    layout: str = "flat"  # flat | modular
    environments: List[str] = field(default_factory=list)  # modular multi-env roots
    enable_backend: bool = True
    enable_bootstrap: bool = True  # emit bootstrap stack for state resources
    generate_ci: bool = True
    generate_policies: bool = True
    generate_oidc: bool = True  # OIDC CI auth recipes
    github_org: str = ""  # e.g. my-org (for OIDC subject)
    github_repo: str = ""  # e.g. my-repo
    provider_version_aws: str = "~> 5.0"
    provider_version_gcp: str = "~> 5.0"
    provider_version_azure: str = "~> 3.0"
    terraform_version: str = ">= 1.5.0"
    terraform_binary: str = "terraform"  # or tofu

    # Tags / labels
    tags: Dict[str, str] = field(default_factory=dict)
    owner: str = ""
    cost_center: str = ""

    # GCP-specific
    gcp_project_id: str = ""  # billing/project id; defaults to project slug

    # Azure-specific
    azure_subscription_id: str = ""

    # Meta
    managed_by: str = "TerraGen"

    def __post_init__(self) -> None:
        self.project = _slug(self.project)
        self.cloud = self.cloud.lower().strip()
        self.environment = self.environment.lower().strip()
        self.blueprint = self.blueprint.lower().strip()
        self.nat_mode = self.nat_mode.lower().strip()
        self.layout = (self.layout or "flat").lower().strip()
        if isinstance(self.ssh_cidrs, str):
            self.ssh_cidrs = [c.strip() for c in self.ssh_cidrs.split(",") if c.strip()]
        if isinstance(self.alert_emails, str):
            self.alert_emails = [
                e.strip() for e in self.alert_emails.split(",") if e.strip()
            ]
        if isinstance(self.environments, str):
            self.environments = [
                e.strip().lower() for e in self.environments.split(",") if e.strip()
            ]
        if isinstance(self.interface_endpoints, str):
            self.interface_endpoints = [
                e.strip() for e in self.interface_endpoints.split(",") if e.strip()
            ]
        self.environments = [e.lower() for e in (self.environments or [])]
        if isinstance(self.spoke_cidrs, str):
            self.spoke_cidrs = [
                c.strip() for c in self.spoke_cidrs.split(",") if c.strip()
            ]
        self.hub_spoke_connectivity = (self.hub_spoke_connectivity or "tgw").lower()
        self._apply_blueprint_defaults()
        self._apply_private_only_defaults()
        self._ensure_interface_endpoints()
        self._ensure_cluster_name()
        self._ensure_spoke_cidrs()
        self._ensure_tags()
        self._ensure_subnets()

    def _apply_blueprint_defaults(self) -> None:
        """Layer opinionated defaults from the selected blueprint."""
        bp = self.blueprint

        if bp == "network-ha":
            if self.nat_mode == "single":
                self.nat_mode = "per_az"
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "network-secure":
            if self.nat_mode != "none":
                self.nat_mode = "per_az"
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            self.enable_nsg_defaults = True
            if self.cloud == "aws":
                self.enable_guardduty = True
            if self.az_count < 2:
                self.az_count = 2
            if not self.ssh_cidrs or self.ssh_cidrs == ["0.0.0.0/0"]:
                self.ssh_cidrs = ["10.0.0.0/8"]

        elif bp == "network-private":
            self.nat_mode = "none"
            self.create_public_subnets = False
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            if self.cloud == "aws":
                self.enable_interface_endpoints = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "network-3tier":
            self.enable_isolated_subnets = True
            if self.nat_mode == "none":
                self.nat_mode = "single"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "eks-ready":
            # Prefer AWS; still generate on others with a generic HA network
            if self.nat_mode != "none":
                self.nat_mode = "per_az"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            self.enable_interface_endpoints = True
            self.enable_eks_subnet_tags = True
            if self.cloud == "aws":
                self.enable_guardduty = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "gke-ready":
            if self.nat_mode == "none":
                self.nat_mode = "single"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_gke_secondary_ranges = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "aks-ready":
            if self.nat_mode != "none":
                self.nat_mode = "per_az"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_nsg_defaults = True
            self.enable_aks_tags = True
            if self.az_count < 2:
                self.az_count = 2

        elif bp == "eks-cluster":
            prev_cloud = self.cloud
            self.cloud = "aws"
            if prev_cloud != "aws" and not is_known_region("aws", self.region):
                self.region = default_region("aws")
            if self.nat_mode != "none":
                self.nat_mode = "per_az"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            self.enable_interface_endpoints = True
            self.enable_eks_subnet_tags = True
            self.enable_cluster = True
            self.enable_guardduty = True
            if self.az_count < 2:
                self.az_count = 2
            if not self.cluster_version:
                self.cluster_version = "1.29"
            if not self.node_instance_type:
                self.node_instance_type = "t3.medium"

        elif bp == "gke-cluster":
            prev_cloud = self.cloud
            self.cloud = "gcp"
            if prev_cloud != "gcp" and not is_known_region("gcp", self.region):
                self.region = default_region("gcp")
            if self.nat_mode == "none":
                self.nat_mode = "single"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_gke_secondary_ranges = True
            self.enable_cluster = True
            if self.az_count < 2:
                self.az_count = 2
            if not self.cluster_version:
                self.cluster_version = "1.29"
            if not self.node_instance_type:
                self.node_instance_type = "e2-medium"

        elif bp == "aks-cluster":
            prev_cloud = self.cloud
            self.cloud = "azure"
            if prev_cloud != "azure" and not is_known_region("azure", self.region):
                self.region = default_region("azure")
            if self.nat_mode != "none":
                self.nat_mode = "per_az"
            self.create_public_subnets = True
            self.enable_flow_logs = True
            self.enable_nsg_defaults = True
            self.enable_aks_tags = True
            self.enable_cluster = True
            if self.az_count < 2:
                self.az_count = 2
            if not self.cluster_version:
                self.cluster_version = "1.29"
            if not self.node_instance_type:
                self.node_instance_type = "Standard_D2s_v3"

        elif bp == "hub-spoke":
            self.enable_hub_spoke = True
            self.enable_flow_logs = True
            self.enable_vpc_endpoints = True
            if self.nat_mode == "none":
                self.nat_mode = "single"
            if self.az_count < 2:
                self.az_count = 2
            # Hub uses hub_cidr as primary VPC CIDR for subnet planning
            if self.hub_cidr:
                self.vpc_cidr = self.hub_cidr
            if self.cloud == "aws":
                self.hub_spoke_connectivity = self.hub_spoke_connectivity or "tgw"
            else:
                self.hub_spoke_connectivity = "peering"

    def _apply_private_only_defaults(self) -> None:
        """When NAT is disabled, prefer private-only usable networking."""
        if self.nat_mode != "none":
            return
        if self.cloud == "aws":
            self.enable_vpc_endpoints = True
            self.enable_interface_endpoints = True
        elif self.cloud == "azure" and not self.create_public_subnets:
            # Azure templates support private-only but keep public if not explicit
            pass

    def _ensure_interface_endpoints(self) -> None:
        if self.enable_interface_endpoints and not self.interface_endpoints:
            self.interface_endpoints = list(DEFAULT_AWS_INTERFACE_ENDPOINTS)

    def _ensure_cluster_name(self) -> None:
        if self.enable_cluster and not self.cluster_name:
            self.cluster_name = f"{self.project}-{self.environment}-k8s"

    def _ensure_spoke_cidrs(self) -> None:
        if not self.enable_hub_spoke:
            return
        # Defer invalid counts to validate_config (avoid hard crash in from_dict)
        if self.spoke_count < 1 or self.spoke_count > 16:
            return
        if self.spoke_cidrs and len(self.spoke_cidrs) >= self.spoke_count:
            self.spoke_cidrs = self.spoke_cidrs[: self.spoke_count]
            return
        # Default spoke CIDRs: 10.1.0.0/16, 10.2.0.0/16, …
        from terragen.cidrs import compute_spoke_cidrs

        self.spoke_cidrs = compute_spoke_cidrs(
            self.hub_cidr or self.vpc_cidr, self.spoke_count
        )

    def _ensure_tags(self) -> None:
        base = {
            "Project": self.project,
            "Environment": self.environment,
            "ManagedBy": self.managed_by,
            "Blueprint": self.blueprint,
        }
        if self.owner:
            base["Owner"] = self.owner
        if self.cost_center:
            base["CostCenter"] = self.cost_center
        if self.enable_eks_subnet_tags:
            base["KubernetesCluster"] = f"{self.project}-{self.environment}"
        if self.enable_aks_tags:
            base["aks-managed"] = "ready"
        if self.enable_gke_secondary_ranges:
            base["gke-ready"] = "true"
        merged = {**base, **(self.tags or {})}
        self.tags = merged

    def _ensure_subnets(self) -> None:
        if self.public_subnets and self.private_subnets:
            validate_custom_subnets(
                self.vpc_cidr,
                self.public_subnets,
                self.private_subnets,
                self.isolated_subnets or None,
            )
            if not self.create_public_subnets:
                self.public_subnets = []
            if not self.enable_isolated_subnets:
                self.isolated_subnets = []
        elif not self.create_public_subnets:
            self.public_subnets = []
            self.private_subnets = compute_private_only_cidrs(self.vpc_cidr, self.az_count)
            self.isolated_subnets = []
        elif self.enable_isolated_subnets:
            public, private, isolated = compute_three_tier_cidrs(
                self.vpc_cidr, self.az_count
            )
            self.public_subnets = public
            self.private_subnets = private
            self.isolated_subnets = isolated
        else:
            public, private = compute_subnet_cidrs(self.vpc_cidr, self.az_count)
            self.public_subnets = public
            self.private_subnets = private
            self.isolated_subnets = []

        if self.enable_gke_secondary_ranges and not (
            self.gke_pod_cidrs and self.gke_service_cidrs
        ):
            pods, svcs = compute_gke_secondary_ranges(self.vpc_cidr, self.az_count)
            self.gke_pod_cidrs = pods
            self.gke_service_cidrs = svcs

    @property
    def enable_nat(self) -> bool:
        return self.nat_mode != "none"

    @property
    def nat_per_az(self) -> bool:
        return self.nat_mode == "per_az"

    @property
    def nat_count(self) -> int:
        if self.nat_mode == "none":
            return 0
        if self.nat_mode == "single":
            return 1
        return self.az_count

    @property
    def gcp_project(self) -> str:
        return self.gcp_project_id or self.project

    @property
    def state_bucket_name(self) -> str:
        # Globally unique-ish; user should still ensure availability.
        raw = f"{self.project}-{self.environment}-tfstate"
        return re.sub(r"[^a-z0-9-]", "", raw.lower())[:63]

    @property
    def state_lock_table(self) -> str:
        return f"{self.project}-{self.environment}-tf-lock"

    @property
    def azure_storage_account(self) -> str:
        # 3-24 chars, alphanumeric only
        raw = re.sub(r"[^a-z0-9]", "", f"{self.project}{self.environment}tf")[:24]
        if len(raw) < 3:
            raw = (raw + "tfstate")[:24]
        return raw

    @property
    def is_modular(self) -> bool:
        return self.layout == "modular"

    @property
    def env_list(self) -> List[str]:
        """Environments to generate roots for (modular layout)."""
        if self.environments:
            return list(dict.fromkeys(self.environments))  # unique, preserve order
        return [self.environment]

    @property
    def private_only(self) -> bool:
        return self.nat_mode == "none" and not self.create_public_subnets

    @property
    def github_repository(self) -> str:
        if self.github_org and self.github_repo:
            return f"{self.github_org}/{self.github_repo}"
        return self.github_repo or "ORG/REPO"

    def cost_estimate(self, estimated_gb_out: float = 100.0) -> dict:
        return estimate_nat_monthly_usd(
            self.cloud, self.az_count, self.nat_mode, estimated_gb_out
        )

    def with_environment(self, environment: str) -> "TerraGenConfig":
        """Return a copy of this config for a different environment root."""
        data = self.to_dict()
        data["environment"] = environment
        # tags will be rebuilt in __post_init__
        data["tags"] = {
            k: v
            for k, v in (self.tags or {}).items()
            if k not in ("Project", "Environment", "ManagedBy", "Blueprint", "Owner", "CostCenter")
        }
        return TerraGenConfig.from_dict(data)

    def to_template_context(self) -> Dict[str, Any]:
        """Flatten config into Jinja context."""
        ctx = asdict(self)
        ctx.update(
            {
                "enable_nat": self.enable_nat,
                "nat_per_az": self.nat_per_az,
                "nat_count": self.nat_count,
                "gcp_project": self.gcp_project,
                "state_bucket_name": self.state_bucket_name,
                "state_lock_table": self.state_lock_table,
                "azure_storage_account": self.azure_storage_account,
                "cost_estimate": self.cost_estimate(),
                "is_modular": self.is_modular,
                "env_list": self.env_list,
                "private_only": self.private_only,
                "github_repository": self.github_repository,
                "module_source": "../../modules/network" if self.is_modular else ".",
                "cluster_module_source": "../../modules/cluster" if self.is_modular else ".",
                # True only when rendering modules/cluster (see render.py)
                "cluster_as_module": False,
                "tags_json": json.dumps(self.tags, indent=2),
                "ssh_cidrs_json": json.dumps(self.ssh_cidrs),
                "public_subnets_json": json.dumps(self.public_subnets),
                "private_subnets_json": json.dumps(self.private_subnets),
                "isolated_subnets_json": json.dumps(self.isolated_subnets),
                "billing_thresholds_json": json.dumps(self.billing_thresholds),
                "alert_emails_json": json.dumps(self.alert_emails),
                "interface_endpoints_json": json.dumps(self.interface_endpoints),
                "gke_pod_cidrs_json": json.dumps(self.gke_pod_cidrs),
                "gke_service_cidrs_json": json.dumps(self.gke_service_cidrs),
                "spoke_cidrs_json": json.dumps(self.spoke_cidrs),
                "cluster_name_effective": self.cluster_name
                or f"{self.project}-{self.environment}-k8s",
            }
        )
        return ctx

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_answers_dict(self) -> Dict[str, Any]:
        """Serializable answers suitable for --answers files."""
        d = self.to_dict()
        # Drop computed subnet lists if they match auto - keep them for reproducibility
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerraGenConfig":
        data = copy.deepcopy(data or {})
        # Accept legacy keys
        if "azs" in data and "az_count" not in data:
            data["az_count"] = data.pop("azs")
        if "enable_nat" in data and "nat_mode" not in data:
            data["nat_mode"] = "single" if data.pop("enable_nat") else "none"
        if "alert_endpoints" in data and "alert_emails" not in data:
            data["alert_emails"] = data.pop("alert_endpoints")
        if data.get("private_only") is True:
            data.setdefault("nat_mode", "none")
            cloud = (data.get("cloud") or "aws").lower()
            if cloud == "aws":
                data.setdefault("create_public_subnets", False)
                data.setdefault("enable_interface_endpoints", True)
            data.setdefault("enable_vpc_endpoints", True)
            data.pop("private_only", None)
        if data.get("layout") == "modules":
            data["layout"] = "modular"

        # Only pass known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}

        # Defaults for region if missing
        cloud = (filtered.get("cloud") or "aws").lower()
        if "region" not in filtered:
            filtered["region"] = default_region(cloud)

        return cls(**filtered)

    @classmethod
    def from_file(cls, path: Path | str) -> "TerraGenConfig":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        data: Any
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml
            except ImportError as e:
                raise ValueError(
                    "PyYAML is required to parse YAML answer files. "
                    "Install with: pip install PyYAML"
                ) from e
            data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"Answers file must be a mapping/object: {path}")
        return cls.from_dict(data)
