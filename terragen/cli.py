"""TerraGen command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from terragen import __author__, __version__
from terragen.blueprints import describe_blueprint, list_blueprints
from terragen.bootstrap_cmd import ensure_bootstrap_generated, find_bootstrap_dir, run_bootstrap
from terragen.config import (
    ENVIRONMENTS,
    LAYOUTS,
    NAT_MODES,
    SUPPORTED_BLUEPRINTS,
    SUPPORTED_CLOUDS,
    TerraGenConfig,
)
from terragen.cost import architecture_cost_report
from terragen.doctor import format_report, run_doctor
from terragen.regions import default_region, list_regions, suggest_regions
from terragen.render import render_project, write_answers_example
from terragen.schema import answers_schema, write_schema
from terragen.validate import validate_config


def _print(msg: str = "") -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _explain(*lines: str) -> None:
    """Print plain-language help above a prompt."""
    for line in lines:
        _print(f"  {line}")


def _section(title: str) -> None:
    _print()
    _print(f"── {title} " + "─" * max(0, 50 - len(title)))


class _Wizard:
    """Tracks progress through the interactive questionnaire."""

    def __init__(self, total: int = 16) -> None:
        self.total = total
        self.n = 0

    def tick(self, label: str = "") -> None:
        self.n += 1
        suffix = f" — {label}" if label else ""
        _print(f"  [{self.n}/{self.total}]{suffix}")


def _ask(prompt: str, default: Optional[str] = None) -> str:
    if default is not None and default != "":
        resp = input(f"{prompt} [{default}]: ").strip()
        return resp or default
    return input(f"{prompt}: ").strip()


def _ask_choice(prompt: str, choices: List[str], default: str) -> str:
    choices_l = [c.lower() for c in choices]
    default = default.lower()
    hint = "/".join(choices)
    while True:
        val = _ask(f"{prompt} ({hint})", default).lower()
        if val in choices_l:
            return val
        _print(f"  Please choose one of: {hint}")


def _ask_bool(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        val = _ask(f"{prompt} [{d}]", "").lower()
        if val == "" and default:
            return True
        if val == "" and not default:
            return False
        if val in ("y", "yes", "true", "1"):
            return True
        if val in ("n", "no", "false", "0"):
            return False
        _print("  Enter y or n")


def _ask_int(prompt: str, default: int, min_v: int = 1, max_v: int = 6) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            n = int(raw)
            if min_v <= n <= max_v:
                return n
            _print(f"  Enter an integer between {min_v} and {max_v}")
        except ValueError:
            _print("  Enter a valid integer")


def interactive_config(*, answers_only: bool = False) -> TerraGenConfig:
    _print()
    _print("=" * 62)
    _print("  TerraGen — multi-cloud Terraform network generator")
    _print(f"  v{__version__}  ·  Created by {__author__}")
    _print("=" * 62)
    _print()
    if answers_only:
        _explain(
            "I'll ask a series of questions, then write an answers YAML file only",
            "(no Terraform project). Use it later with: terragen generate -a <file>",
            "Press Enter to accept the default shown in [brackets].",
            "Ctrl+C cancels without writing files.",
        )
    else:
        _explain(
            "I'll ask a series of questions, then write Terraform files for a cloud network.",
            "Press Enter to accept the default shown in [brackets].",
            "Ctrl+C cancels without writing files.",
            "You can re-run later with an answers file for non-interactive use.",
        )
    wiz = _Wizard(total=18)

    # ── Identity ──────────────────────────────────────────────
    _section("Project basics")
    wiz.tick("project name")
    _explain(
        "Project name is a short label used in resource names (e.g. my-app-dev-vpc).",
        "Use lowercase letters, numbers, and hyphens only (3–40 characters).",
    )
    project = _ask("Project name", "my-cloud-project")

    wiz.tick("cloud")
    _explain(
        "Which cloud you want to deploy into. TerraGen will emit native resources",
        "for that provider (AWS VPC, GCP VPC, or Azure VNet).",
        "  aws   — Amazon Web Services",
        "  gcp   — Google Cloud Platform",
        "  azure — Microsoft Azure",
    )
    cloud = _ask_choice("Cloud provider", list(SUPPORTED_CLOUDS), "aws")

    wiz.tick("region")
    _explain(
        "Region (or Azure location) is where the network lives. Pick one close to",
        "your users for lower latency. Suggested common regions:",
        f"  {', '.join(suggest_regions(cloud, 8))}",
    )
    region = _ask("Region / location", default_region(cloud))

    wiz.tick("environment")
    _explain(
        "Environment labels this stack (dev, staging, prod, shared).",
        "It is added to names and tags so you can tell environments apart.",
    )
    environment = _ask_choice("Environment", list(ENVIRONMENTS), "dev")

    # ── Layout ────────────────────────────────────────────────
    _section("Project layout")
    wiz.tick("layout")
    _explain(
        "How Terraform files are organized on disk:",
        "  flat     — one folder; simplest for a single environment",
        "  modular  — shared modules/network + envs/dev, envs/prod, …",
        "             better when you share one network design across envs",
    )
    layout = _ask_choice("Project layout", list(LAYOUTS), "flat")
    environments: List[str] = []
    if layout == "modular":
        wiz.tick("env list")
        _explain(
            "Which environment folders to create under envs/.",
            "Example: dev,staging,prod → three thin roots that call the same module.",
        )
        env_raw = _ask("Environments to generate (comma-separated)", "dev,staging,prod")
        environments = [e.strip() for e in env_raw.split(",") if e.strip()]

    # ── Blueprint ─────────────────────────────────────────────
    _section("Blueprint (starter package)")
    wiz.tick("blueprint")
    cloud_bps = [b["id"] for b in list_blueprints(cloud)]
    # Always allow all blueprints but highlight cloud-native ones first
    _explain("A blueprint is an opinionated preset. Recommended for this cloud first:")
    for bp in list_blueprints(cloud):
        _print(f"  ★ {bp['id']:16} — {bp['summary']}")
    _explain("Other blueprints (still available):")
    for bp in list_blueprints():
        if bp["id"] not in cloud_bps:
            _print(f"    {bp['id']:16} — {bp['summary']}")
    _explain(
        "Quick guide:",
        "  network / network-ha / network-secure — general purpose",
        "  network-private — no public subnets / no NAT",
        "  network-3tier   — public + app + isolated data subnets",
        "  eks-ready / gke-ready / aks-ready — Kubernetes network prep",
        "  eks-cluster / gke-cluster / aks-cluster — full managed K8s",
        "  hub-spoke       — hub VPC + multiple spoke networks",
    )
    blueprint = _ask_choice("Blueprint", list(SUPPORTED_BLUEPRINTS), "network")

    # ── Addressing ────────────────────────────────────────────
    _section("Network size & shape")
    wiz.tick("CIDR")
    _explain(
        "VPC/VNet CIDR is the private IP range for your whole network.",
        "Use a private range that won't clash with other networks you peer later.",
        "  Common picks: 10.0.0.0/16 (65k IPs) or 10.10.0.0/16",
        "  Avoid 10.0.0.0/8-wide ranges that overlap VPN / office networks.",
    )
    vpc_cidr = _ask("VPC / VNet CIDR", "10.0.0.0/16")

    wiz.tick("AZs")
    _explain(
        "Availability zones (AZs) are separate data centers in a region.",
        "TerraGen creates a public + private subnet pair per AZ (unless private-only).",
        "  2 = good default for HA   |   3 = more resilience, higher NAT cost if per_az",
        "  1 = cheapest, no multi-AZ resilience",
    )
    az_count = _ask_int("Number of AZs / subnet pairs", 2, 1, 6)

    # ── Connectivity ──────────────────────────────────────────
    _section("Internet access (NAT & public subnets)")
    wiz.tick("private-only / NAT")
    # Blueprints that already imply private-only skip the question
    if blueprint == "network-private":
        private_only = True
        _explain("Blueprint network-private implies private-only (no public subnets / NAT).")
    else:
        _explain(
            "Private-only means: no public subnets and no NAT gateway.",
            "Workloads stay private; on AWS we add VPC endpoints so they can still",
            "reach services like S3, SSM, ECR, and CloudWatch without the public internet.",
            "Choose Yes for locked-down production apps; No if you need public load balancers",
            "or outbound internet via NAT (most typical app networks).",
        )
        private_only = _ask_bool("Private-only network?", False)
    if private_only:
        nat_mode = "none"
        create_public = False
        _explain("→ Using nat_mode=none and no public subnets.")
    else:
        _explain(
            "NAT lets private subnets reach the internet (updates, APIs) without",
            "exposing those instances with a public IP.",
            "  none    — no NAT (cheapest; private hosts can't reach the internet)",
            "  single  — one NAT shared by all AZs (good cost/HA balance for many apps)",
            "  per_az  — one NAT per AZ (best HA; roughly N× the idle NAT cost)",
        )
        nat_mode = _ask_choice("NAT mode", list(NAT_MODES), "single")
        create_public = True

    # ── Observability / endpoints ─────────────────────────────
    _section("Logging & private access to cloud services")
    wiz.tick("flow logs")
    _explain(
        "Flow logs record network traffic metadata (who talked to whom).",
        "Useful for troubleshooting and security review. Small ongoing cost for storage.",
    )
    enable_flow_logs = _ask_bool("Enable flow logs?", True)

    wiz.tick("gateway endpoints")
    _explain(
        "Gateway VPC endpoints (AWS) let traffic to S3 and DynamoDB stay inside AWS",
        "instead of going through NAT — saves money and improves security.",
        "On other clouds this is mostly a no-op or future-facing flag.",
    )
    enable_vpc_endpoints = _ask_bool(
        "Enable gateway VPC endpoints (S3/DynamoDB on AWS)?",
        private_only or blueprint not in ("network",),
    )
    enable_interface = False
    if cloud == "aws":
        wiz.tick("interface endpoints")
        _explain(
            "Interface endpoints create private ENIs for AWS APIs (SSM, ECR, logs,",
            "STS, KMS, Secrets Manager, …). Strongly recommended for private-only",
            "and EKS-ready networks so nodes can pull images without NAT.",
            "Each endpoint has a small hourly cost.",
        )
        enable_interface = _ask_bool(
            "Enable interface endpoints pack?",
            private_only or blueprint in ("eks-ready", "network-private", "network-secure"),
        )

    # ── Security ──────────────────────────────────────────────
    _section("Security")
    wiz.tick("bastion")
    _explain(
        "A bastion / management security group allows SSH (port 22) from chosen IPs.",
        "Default is OFF. Only enable if you plan a jump host or similar.",
        "Never open SSH to 0.0.0.0/0 in production.",
    )
    enable_bastion_sg = _ask_bool("Create bastion/management security group?", False)
    ssh_cidrs = ["10.0.0.0/8"]
    if enable_bastion_sg:
        _explain(
            "CIDR blocks allowed to SSH. Examples:",
            "  10.0.0.0/8          — your private networks",
            "  203.0.113.10/32    — a single office public IP",
            "Comma-separate multiple ranges.",
        )
        ssh_raw = _ask("SSH allow CIDRs (comma-separated)", "10.0.0.0/8")
        ssh_cidrs = [c.strip() for c in ssh_raw.split(",") if c.strip()]

    enable_guardduty = False
    if cloud == "aws":
        wiz.tick("GuardDuty")
        _explain(
            "Amazon GuardDuty is a threat-detection service that watches for",
            "suspicious activity in your account. Small cost; good for production.",
        )
        enable_guardduty = _ask_bool(
            "Enable GuardDuty?",
            blueprint in ("network-secure", "eks-ready"),
        )

    wiz.tick("billing alerts")
    _explain(
        "Billing alert scaffolding creates SNS topics + CloudWatch alarms",
        "(AWS billing metrics are in us-east-1). You still confirm email subscriptions.",
        "Helpful so you notice unexpected spend early.",
    )
    enable_billing = _ask_bool("Configure billing alert scaffolding?", False)
    alert_emails: List[str] = []
    billing_thresholds = {"low": 50.0, "medium": 200.0, "high": 500.0}
    if enable_billing:
        _explain(
            "Emails that will be subscribed to alert topics (you must confirm the link).",
        )
        emails = _ask("Alert emails (comma-separated)", "")
        alert_emails = [e.strip() for e in emails.split(",") if e.strip()]

    # ── Tags ──────────────────────────────────────────────────
    _section("Tags (optional metadata)")
    wiz.tick("tags")
    _explain(
        "Owner is a free-text tag (person or team) for cost and ownership tracking.",
    )
    owner = _ask("Owner tag (optional)", "")
    _explain(
        "Cost center / finance code if your org charges back cloud spend.",
    )
    cost_center = _ask("Cost center tag (optional)", "")

    # ── Cloud-specific IDs ────────────────────────────────────
    gcp_project_id = ""
    if cloud == "gcp":
        _section("Google Cloud")
        wiz.tick("GCP project")
        _explain(
            "GCP project ID is the billing/API project (often like my-company-123).",
            "It is not the same as the TerraGen project name unless you made them match.",
        )
        gcp_project_id = _ask("GCP project ID", project)

    azure_subscription_id = ""
    if cloud == "azure":
        _section("Azure")
        wiz.tick("Azure subscription")
        _explain(
            "Optional Azure subscription GUID. Leave blank to use whatever",
            "your local Azure CLI / env is already logged into.",
        )
        azure_subscription_id = _ask("Azure subscription ID (optional)", "")

    # ── GitHub / CI identity ──────────────────────────────────
    _section("GitHub (for CI OIDC — optional)")
    wiz.tick("GitHub")
    _explain(
        "If you use GitHub Actions, TerraGen can generate an oidc/ stack so CI",
        "authenticates with short-lived cloud roles instead of long-lived keys.",
        "Leave blank if you are not wiring CI yet.",
    )
    github_org = _ask("GitHub org or user", "")
    github_repo = _ask("GitHub repository name", "")

    # ── Packaging extras ──────────────────────────────────────
    _section("State, CI, and policies")
    wiz.tick("backend")
    _explain(
        "Remote state stores Terraform's memory of what exists in a cloud bucket",
        "(S3 / GCS / Azure Storage) so the team shares one source of truth.",
        "Recommended for anything beyond a personal experiment.",
    )
    enable_backend = _ask_bool("Generate remote state backend config?", True)
    if enable_backend:
        _explain(
            "Bootstrap is a tiny separate stack that creates the state bucket/table",
            "first (Terraform cannot store state in a backend that does not exist yet).",
            "You apply bootstrap once, then init the main stack against it.",
        )
        enable_bootstrap = _ask_bool("Generate bootstrap stack for state resources?", True)
    else:
        enable_bootstrap = False

    wiz.tick("CI / policies / OIDC")
    _explain(
        "CI stubs are starter GitHub Actions / GitLab CI files that run",
        "terraform fmt, validate, and plan. You still add cloud credentials/OIDC.",
    )
    generate_ci = _ask_bool("Generate CI workflow stubs?", True)

    _explain(
        "Policy stubs are starter Checkov + TFLint configs for static security checks",
        "before you apply. Optional but useful in teams.",
    )
    generate_policies = _ask_bool("Generate Checkov/TFLint policy stubs?", True)

    _explain(
        "OIDC identity stack creates cloud roles/apps so GitHub Actions can deploy",
        "without storing permanent access keys. Pair with github_org/repo above.",
    )
    generate_oidc = _ask_bool("Generate OIDC / federated CI identity stack?", True)

    # IPv6 / hub-spoke extras (short)
    _section("Advanced networking")
    _explain(
        "IPv6 dual-stack assigns IPv6 CIDRs to VPC/subnets (AWS/GCP/Azure).",
        "Useful for modern dual-stack apps; leave off if you only need IPv4.",
    )
    enable_ipv6 = _ask_bool("Enable IPv6 dual-stack?", False)

    spoke_count = 2
    hub_cidr = vpc_cidr
    if blueprint == "hub-spoke":
        _explain(
            "Hub-and-spoke creates one hub network plus isolated spoke networks.",
            "AWS uses Transit Gateway by default; GCP/Azure use peering.",
        )
        spoke_count = _ask_int("Number of spoke networks", 2, 1, 8)
        hub_cidr = _ask("Hub network CIDR", vpc_cidr)

    data = {
        "project": project,
        "cloud": cloud,
        "region": region,
        "environment": environment,
        "layout": layout,
        "environments": environments,
        "blueprint": blueprint,
        "vpc_cidr": vpc_cidr,
        "az_count": az_count,
        "nat_mode": nat_mode,
        "create_public_subnets": create_public,
        "enable_flow_logs": enable_flow_logs,
        "enable_vpc_endpoints": enable_vpc_endpoints,
        "enable_interface_endpoints": enable_interface,
        "enable_bastion_sg": enable_bastion_sg,
        "ssh_cidrs": ssh_cidrs,
        "enable_guardduty": enable_guardduty,
        "enable_billing_alerts": enable_billing,
        "billing_thresholds": billing_thresholds,
        "alert_emails": alert_emails,
        "owner": owner,
        "cost_center": cost_center,
        "gcp_project_id": gcp_project_id,
        "azure_subscription_id": azure_subscription_id,
        "github_org": github_org,
        "github_repo": github_repo,
        "enable_backend": enable_backend,
        "enable_bootstrap": enable_bootstrap,
        "generate_ci": generate_ci,
        "generate_policies": generate_policies,
        "generate_oidc": generate_oidc,
        "enable_ipv6": enable_ipv6,
        "spoke_count": spoke_count,
        "hub_cidr": hub_cidr,
    }
    cfg = TerraGenConfig.from_dict(data)

    # ── Summary + confirm ─────────────────────────────────────
    _section("Summary — review before writing")
    est = cfg.cost_estimate()
    _print(f"  Project:      {cfg.project}")
    _print(f"  Cloud:        {cfg.cloud} / {cfg.region} / env={cfg.environment}")
    _print(f"  Blueprint:    {cfg.blueprint}  |  layout={cfg.layout}")
    if cfg.is_modular:
        _print(f"  Env roots:    {', '.join(cfg.env_list)}")
    _print(f"  CIDR:         {cfg.vpc_cidr}  |  AZs={cfg.az_count}")
    _print(f"  Public:       {cfg.public_subnets or '(none)'}")
    _print(f"  Private:      {cfg.private_subnets}")
    if cfg.isolated_subnets:
        _print(f"  Isolated:     {cfg.isolated_subnets}")
    _print(f"  NAT:          {cfg.nat_mode} ({est['gateways']} gateway(s), ~${est['monthly_usd_low']}/mo idle)")
    _print(f"  IPv6:         {cfg.enable_ipv6}")
    if cfg.enable_cluster:
        _print(f"  Cluster:      {cfg.cluster_name} (v{cfg.cluster_version})")
    if cfg.enable_hub_spoke:
        _print(f"  Hub-spoke:    hub={cfg.hub_cidr} spokes={cfg.spoke_count} via {cfg.hub_spoke_connectivity}")
    _print(
        f"  Features:     flow_logs={cfg.enable_flow_logs}  "
        f"gw_endpoints={cfg.enable_vpc_endpoints}  "
        f"if_endpoints={cfg.enable_interface_endpoints}"
    )
    _print(
        f"  Packaging:    backend={cfg.enable_backend}  bootstrap={cfg.enable_bootstrap}  "
        f"ci={cfg.generate_ci}  oidc={cfg.generate_oidc}"
    )
    _print()
    confirm = (
        "Write answers file with these settings?"
        if answers_only
        else "Generate files with these settings?"
    )
    if not _ask_bool(confirm, True):
        _print("Cancelled — no files written.")
        raise SystemExit(0)

    _print()
    if answers_only:
        _explain("Writing answers file…")
    else:
        _explain("Generating your Terraform project…")
    _print()
    return cfg


def _build_config(args: argparse.Namespace) -> TerraGenConfig:
    if args.answers:
        cfg = TerraGenConfig.from_file(args.answers)
        overrides = _overrides_from_args(args)
        if overrides:
            merged = cfg.to_dict()
            merged.update(overrides)
            cfg = TerraGenConfig.from_dict(merged)
        return cfg
    if getattr(args, "non_interactive", False) or (
        getattr(args, "cloud", None)
        or getattr(args, "project", None)
        or getattr(args, "region", None)
    ):
        return TerraGenConfig.from_dict(_overrides_from_args(args) or {})
    return interactive_config()


def cmd_generate(args: argparse.Namespace) -> int:
    cfg = _build_config(args)

    result = validate_config(cfg)
    for w in result.warnings:
        _err(f"Warning: {w}")
    if not result.ok:
        for e in result.errors:
            _err(f"Error: {e}")
        return 1

    outdir = (
        Path(args.out)
        if args.out
        else Path.cwd() / f"{cfg.project}-{cfg.environment}-terraform"
    )

    if args.dry_run:
        _print(f"[dry-run] Would generate {cfg.cloud} project into: {outdir}")
        _print(
            f"  layout={cfg.layout} blueprint={cfg.blueprint} "
            f"az_count={cfg.az_count} nat_mode={cfg.nat_mode}"
        )
        if cfg.is_modular:
            _print(f"  environments={cfg.env_list}")
        _print(f"  public={cfg.public_subnets}")
        _print(f"  private={cfg.private_subnets}")
        _print()
        _print(architecture_cost_report(cfg))
        plan = render_project(cfg, outdir, force=args.force, dry_run=True)
        _print(f"  files: {len(plan.files_written)}")
        for f in plan.relative_files:
            _print(f"    - {f}")
        return 0

    try:
        rendered = render_project(cfg, outdir, force=args.force, dry_run=False)
    except FileExistsError as e:
        _err(str(e))
        return 1
    except Exception as e:
        _err(f"Generation failed: {e}")
        return 1

    _print()
    _print(f"✓ Generated Terraform project in: {outdir}")
    _print(
        f"  Cloud: {cfg.cloud} | Layout: {cfg.layout} | "
        f"Blueprint: {cfg.blueprint} | Env: {cfg.environment}"
    )
    if cfg.is_modular:
        _print(f"  Environment roots: {', '.join(cfg.env_list)}")
    _print(f"  Files written: {len(rendered.files_written)}")
    if rendered.skipped:
        for s in rendered.skipped:
            _err(f"  Skipped: {s}")
    _print()
    _print(architecture_cost_report(cfg))
    _print()
    _print(
        f"  Re-run later: python -m terragen generate -a {outdir / 'terragen.answers.yaml'} "
        f"--out {outdir} --force"
    )
    _print()
    _print_next_steps(outdir, cfg)

    if getattr(args, "validate", False):
        return _run_terraform_validate(outdir, cfg)
    return 0


def _run_terraform_validate(outdir: Path, cfg: TerraGenConfig) -> int:
    """Run terraform fmt/validate if binary is available."""
    import shutil
    import subprocess

    binary = cfg.terraform_binary if shutil.which(cfg.terraform_binary) else None
    if not binary:
        binary = "terraform" if shutil.which("terraform") else None
    if not binary:
        binary = "tofu" if shutil.which("tofu") else None
    if not binary:
        _err("Warning: --validate requested but terraform/tofu not on PATH; skipped.")
        return 0

    work = outdir / f"envs/{cfg.environment}" if cfg.is_modular else outdir
    _print(f"Running {binary} validate in {work} …")
    steps = [
        ([binary, "fmt", "-check", "-recursive"], str(outdir)),
        ([binary, "init", "-backend=false", "-input=false"], str(work)),
        ([binary, "validate"], str(work)),
    ]
    for args, cwd in steps:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
        if p.returncode != 0 and args[1] == "fmt":
            # Auto-format once, then re-check is optional; warn only
            subprocess.run(
                [binary, "fmt", "-recursive"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            continue
        if p.returncode != 0:
            _err(p.stdout or "")
            _err(p.stderr or "")
            _err(f"{binary} {' '.join(args[1:])} failed (cwd={cwd})")
            return p.returncode
    _print(f"✓ {binary} validate succeeded")
    return 0


def _print_next_steps(outdir: Path, cfg: TerraGenConfig) -> None:
    _print("Next steps:")
    step = 1
    _print(f"  {step}. cd {outdir}")
    step += 1
    if cfg.enable_bootstrap and cfg.enable_backend:
        _print(
            f"  {step}. terragen bootstrap --project-dir .   "
            f"# or: cd bootstrap && terraform apply"
        )
        step += 1
    work = f"envs/{cfg.environment}" if cfg.is_modular else "."
    _print(f"  {step}. cd {work} && terraform init")
    step += 1
    _print(f"  {step}. terraform plan && terraform apply")
    if cfg.generate_oidc:
        step += 1
        _print(f"  {step}. (optional) cd oidc && terraform apply  # CI OIDC role")
    _print()


def _overrides_from_args(args: argparse.Namespace) -> dict:
    mapping = {
        "project": "project",
        "cloud": "cloud",
        "region": "region",
        "environment": "environment",
        "blueprint": "blueprint",
        "vpc_cidr": "vpc_cidr",
        "az_count": "az_count",
        "nat_mode": "nat_mode",
        "owner": "owner",
        "gcp_project_id": "gcp_project_id",
        "layout": "layout",
        "github_org": "github_org",
        "github_repo": "github_repo",
    }
    out = {}
    for attr, key in mapping.items():
        val = getattr(args, attr, None)
        if val is not None:
            out[key] = val
    if getattr(args, "environments", None):
        out["environments"] = [
            e.strip() for e in args.environments.split(",") if e.strip()
        ]
    if getattr(args, "private_only", False):
        out["private_only"] = True
    if getattr(args, "no_backend", False):
        out["enable_backend"] = False
        out["enable_bootstrap"] = False
    if getattr(args, "no_ci", False):
        out["generate_ci"] = False
    if getattr(args, "no_policies", False):
        out["generate_policies"] = False
    if getattr(args, "no_oidc", False):
        out["generate_oidc"] = False
    if getattr(args, "interface_endpoints", False):
        out["enable_interface_endpoints"] = True
    if getattr(args, "ipv6", False):
        out["enable_ipv6"] = True
    if getattr(args, "spoke_count", None) is not None:
        out["spoke_count"] = args.spoke_count
        out["enable_hub_spoke"] = True
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = TerraGenConfig.from_file(args.answers)
    result = validate_config(cfg)
    for w in result.warnings:
        _print(f"Warning: {w}")
    if result.ok:
        _print("Configuration is valid.")
        _print(f"  project={cfg.project} cloud={cfg.cloud} region={cfg.region}")
        _print(
            f"  layout={cfg.layout} blueprint={cfg.blueprint} nat_mode={cfg.nat_mode}"
        )
        _print(f"  public_subnets={cfg.public_subnets}")
        _print(f"  private_subnets={cfg.private_subnets}")
        return 0
    for e in result.errors:
        _err(f"Error: {e}")
    return 1


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Generate (if needed) and run terraform against bootstrap/."""
    project_dir = Path(args.project_dir or ".")
    binary = args.binary or "terraform"

    boot = find_bootstrap_dir(project_dir)
    if not boot or not boot.exists():
        if not args.answers and not args.project:
            _err(
                "No bootstrap/ found. Pass --answers to generate a project, "
                "or --project-dir pointing at a TerraGen output."
            )
            return 1
        # Synthesize generate
        class _A:
            pass

        a = _A()
        for k, v in vars(args).items():
            setattr(a, k, v)
        a.force = True
        a.out = str(project_dir if args.project_dir else Path.cwd() / "bootstrap-out")
        a.dry_run = False
        a.non_interactive = True
        cfg = _build_config(a)
        cfg.enable_backend = True
        cfg.enable_bootstrap = True
        out = Path(a.out)
        _print(f"Generating project with bootstrap into {out} …")
        try:
            boot = ensure_bootstrap_generated(cfg, out, force=True)
        except Exception as e:
            _err(str(e))
            return 1
        project_dir = out
    else:
        boot = Path(boot)

    _print(f"Bootstrap directory: {boot}")
    if args.dry_run:
        code, log = run_bootstrap(boot, binary=binary, dry_run=True)
        _print(log)
        return code

    code, log = run_bootstrap(
        boot, binary=binary, auto_approve=args.auto_approve, dry_run=False
    )
    _print(log)
    if code == 0 and args.auto_approve:
        _print("✓ Remote state backend resources applied.")
        _print(f"  Next: cd {project_dir} && terraform init")
    return code


def cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(Path(args.project_dir) if args.project_dir else None)
    _print(format_report(report))
    return 0 if report.ok else 1


def cmd_import(args: argparse.Namespace) -> int:
    """Brownfield: discover existing network and emit import blocks."""
    from terragen.import_brownfield import (
        discover_aws_vpc,
        generate_import_project,
        load_inventory,
    )

    outdir = Path(args.out or "./imported-network")
    try:
        if args.inventory:
            disc = load_inventory(Path(args.inventory))
        elif args.cloud == "aws" and args.vpc_id:
            _print(f"Discovering AWS VPC {args.vpc_id} in {args.region} …")
            disc = discover_aws_vpc(args.vpc_id, args.region or "us-east-1")
        else:
            _err(
                "Provide either:\n"
                "  --inventory path/to/inventory.json   "
                "(AWS, GCP, or Azure — see examples/inventory-*-sample.json)\n"
                "  or --cloud aws --vpc-id vpc-xxxxxxxx [--region us-east-1]  "
                "(live AWS only; needs boto3)"
            )
            return 1

        if args.dry_run:
            _print(json.dumps(disc.to_dict(), indent=2))
            return 0

        written = generate_import_project(disc, outdir)
        counts = disc.summary_counts()
        _print(f"✓ Brownfield import project written to: {outdir}")
        _print(
            f"  Cloud: {disc.cloud}  network: {disc.network_name()}  "
            f"CIDR/space: {disc.vpc_cidr}  region: {disc.region or '(n/a)'}"
        )
        if disc.cloud == "gcp":
            _print(f"  GCP project: {disc.project_id}")
            _print(
                "  Inventory: "
                f"subnets={counts['subnets']} routers={counts['routers']} "
                f"firewalls={counts['firewalls']}"
            )
        elif disc.cloud == "azure":
            _print(f"  Resource group: {disc.resource_group}")
            _print(
                "  Inventory: "
                f"subnets={counts['subnets']} nsg={counts['network_security_groups']} "
                f"rt={counts['route_tables']} pip={counts['public_ips']} "
                f"nat={counts['nat_gateways']}"
            )
        else:
            _print(
                "  Discovered: "
                f"subnets={counts['subnets']} igw={counts['internet_gateways']} "
                f"nat={counts['nat_gateways']} eip={counts['eips']} "
                f"rtb={counts['route_tables']} rta={counts['route_table_associations']} "
                f"sg={counts['security_groups']} nacl={counts['network_acls']} "
                f"vpce={counts['vpc_endpoints']}"
            )
        _print(f"  Files: {len(written)}")
        _print()
        _print("Next steps:")
        _print(f"  1. cd {outdir}")
        _print("  2. Review imports.tf + *.tf against reality (fix sample IDs if needed)")
        _print("  3. terraform init && terraform plan")
        _print("  4. Fix remaining drift, then apply to bind state")
        if disc.cloud != "aws":
            _print(
                "  Note: live discovery is AWS-only; GCP/Azure use inventory JSON "
                "(see examples/inventory-gcp-sample.json, inventory-azure-sample.json)."
            )
        return 0
    except Exception as e:
        _err(f"Import failed: {e}")
        return 1


def cmd_schema(args: argparse.Namespace) -> int:
    if args.out:
        path = write_schema(args.out)
        _print(f"Wrote JSON Schema to {path}")
        return 0
    _print(json.dumps(answers_schema(), indent=2))
    return 0


def cmd_list_regions(args: argparse.Namespace) -> int:
    cloud = args.cloud.lower()
    if cloud not in SUPPORTED_CLOUDS:
        _err(f"Unknown cloud: {cloud}")
        return 1
    for r in list_regions(cloud):
        _print(f"{r['code']:24} {r['name']}")
    return 0


def cmd_list_blueprints(_: argparse.Namespace) -> int:
    for bp in list_blueprints():
        _print(f"{bp['id']:16} {bp['name']}")
        _print(f"  {bp['summary']}")
        _print()
    return 0


def cmd_describe_blueprint(args: argparse.Namespace) -> int:
    try:
        _print(describe_blueprint(args.blueprint))
        return 0
    except KeyError as e:
        _err(str(e))
        return 1


def cmd_cost(args: argparse.Namespace) -> int:
    if args.answers:
        cfg = TerraGenConfig.from_file(args.answers)
    else:
        cfg = TerraGenConfig.from_dict(
            {
                "cloud": args.cloud or "aws",
                "az_count": args.az_count or 2,
                "nat_mode": args.nat_mode or "single",
            }
        )
    _print(architecture_cost_report(cfg, estimated_gb_out=args.gb or 100.0))
    return 0


def cmd_init_answers(args: argparse.Namespace) -> int:
    """Write answers YAML: static sample or interactive Q&A (no Terraform project)."""
    path = Path(args.out or "answers.yaml")
    if path.exists() and not args.force:
        _err(f"{path} exists. Use --force to overwrite.")
        return 1

    if getattr(args, "interactive", False):
        try:
            cfg = interactive_config(answers_only=True)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            return code if code is not None else 1

        result = validate_config(cfg)
        for w in result.warnings:
            _err(f"Warning: {w}")
        if not result.ok:
            for e in result.errors:
                _err(f"Error: {e}")
            return 1

        try:
            write_answers_example(path, cfg)
        except Exception as e:
            _err(f"Failed to write answers file: {e}")
            return 1

        _print(f"✓ Wrote answers from Q&A: {path}")
        _print()
        _print("Next steps:")
        _print(f"  python -m terragen validate --answers {path}")
        _print(f"  python -m terragen generate --answers {path} --out ./my-network --force")
        return 0

    write_answers_example(path)
    _print(f"Wrote sample answers file: {path}")
    _print("  Tip: use --interactive to build this file from the Q&A wizard (no Terraform output).")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    _print(f"TerraGen {__version__} — Created by {__author__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terragen",
        description=(
            "TerraGen — world-class multi-cloud Terraform network generator "
            f"(AWS, GCP, Azure). Created by {__author__}."
        ),
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    sub = parser.add_subparsers(dest="command")

    def add_gen_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--answers", "-a", help="JSON or YAML answers file")
        p.add_argument("--out", "-o", help="Output directory")
        p.add_argument(
            "--force", "-f", action="store_true", help="Overwrite existing TerraGen project"
        )
        p.add_argument("--dry-run", action="store_true", help="Show what would be generated")
        p.add_argument(
            "--non-interactive",
            action="store_true",
            help="Do not prompt; use defaults/flags",
        )
        p.add_argument("--project", help="Project name")
        p.add_argument("--cloud", choices=SUPPORTED_CLOUDS, help="Cloud provider")
        p.add_argument("--region", help="Region / location")
        p.add_argument("--environment", choices=list(ENVIRONMENTS), help="Environment name")
        p.add_argument(
            "--environments",
            help="Comma-separated envs for modular layout (e.g. dev,staging,prod)",
        )
        p.add_argument("--blueprint", choices=list(SUPPORTED_BLUEPRINTS), help="Blueprint")
        p.add_argument("--layout", choices=list(LAYOUTS), help="flat or modular")
        p.add_argument("--vpc-cidr", dest="vpc_cidr", help="VPC/VNet CIDR")
        p.add_argument("--az-count", dest="az_count", type=int, help="Number of AZs")
        p.add_argument("--nat-mode", dest="nat_mode", choices=list(NAT_MODES), help="NAT mode")
        p.add_argument(
            "--private-only",
            action="store_true",
            help="No NAT, no public subnets, enable private endpoint pack",
        )
        p.add_argument(
            "--interface-endpoints",
            action="store_true",
            help="Enable AWS interface VPC endpoints pack",
        )
        p.add_argument("--owner", help="Owner tag")
        p.add_argument("--gcp-project-id", dest="gcp_project_id", help="GCP project ID")
        p.add_argument("--github-org", dest="github_org", help="GitHub org for OIDC")
        p.add_argument("--github-repo", dest="github_repo", help="GitHub repo for OIDC")
        p.add_argument("--no-backend", action="store_true", help="Skip remote backend files")
        p.add_argument("--no-ci", action="store_true", help="Skip CI workflow generation")
        p.add_argument("--no-policies", action="store_true", help="Skip policy stubs")
        p.add_argument("--no-oidc", action="store_true", help="Skip OIDC identity stack")
        p.add_argument(
            "--validate",
            action="store_true",
            help="After generate, run terraform/tofu fmt + validate if installed",
        )
        p.add_argument(
            "--ipv6",
            action="store_true",
            help="Enable IPv6 dual-stack on the generated network",
        )
        p.add_argument(
            "--spoke-count",
            dest="spoke_count",
            type=int,
            help="Hub-spoke: number of spoke networks",
        )

    g = sub.add_parser("generate", help="Generate a Terraform project (default command)")
    add_gen_flags(g)
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="Validate an answers file")
    v.add_argument("--answers", "-a", required=True, help="JSON or YAML answers file")
    v.set_defaults(func=cmd_validate)

    boot = sub.add_parser(
        "bootstrap",
        help="Create remote state backend (generate if needed, then terraform apply)",
    )
    boot.add_argument("--answers", "-a", help="Answers file (generate project if needed)")
    boot.add_argument(
        "--project-dir",
        "-d",
        help="Existing TerraGen project directory (contains bootstrap/)",
    )
    boot.add_argument("--out", "-o", help="Output dir when generating")
    boot.add_argument("--project", help="Project name when generating without answers")
    boot.add_argument("--cloud", choices=SUPPORTED_CLOUDS)
    boot.add_argument("--region")
    boot.add_argument("--environment", choices=list(ENVIRONMENTS))
    boot.add_argument("--binary", default="terraform", help="terraform or tofu")
    boot.add_argument(
        "--auto-approve", action="store_true", help="Apply without confirmation"
    )
    boot.add_argument("--dry-run", action="store_true")
    boot.set_defaults(func=cmd_bootstrap)

    doc = sub.add_parser("doctor", help="Check local environment health")
    doc.add_argument(
        "--project-dir", "-d", help="Optional generated project to inspect"
    )
    doc.set_defaults(func=cmd_doctor)

    imp = sub.add_parser(
        "import",
        help="Brownfield: discover existing VPC and emit Terraform import project",
    )
    imp.add_argument("--cloud", choices=SUPPORTED_CLOUDS, help="Cloud provider")
    imp.add_argument("--vpc-id", dest="vpc_id", help="AWS VPC ID (vpc-…)")
    imp.add_argument("--region", help="Region for live discovery")
    imp.add_argument(
        "--inventory",
        "-i",
        help="JSON inventory file (from prior discovery or hand-written)",
    )
    imp.add_argument("--out", "-o", default="./imported-network", help="Output directory")
    imp.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered inventory JSON without writing files",
    )
    imp.set_defaults(func=cmd_import)

    sch = sub.add_parser("schema", help="Print or write JSON Schema for answers files")
    sch.add_argument("--out", "-o", help="Write schema to this path")
    sch.set_defaults(func=cmd_schema)

    r = sub.add_parser("regions", help="List curated regions for a cloud")
    r.add_argument("cloud", choices=SUPPORTED_CLOUDS)
    r.set_defaults(func=cmd_list_regions)

    b = sub.add_parser("blueprints", help="List available blueprints")
    b.set_defaults(func=cmd_list_blueprints)

    bd = sub.add_parser("blueprint", help="Describe a blueprint")
    bd.add_argument("blueprint", choices=list(SUPPORTED_BLUEPRINTS))
    bd.set_defaults(func=cmd_describe_blueprint)

    c = sub.add_parser("cost", help="Estimate NAT-related monthly cost")
    c.add_argument("--answers", "-a", help="Answers file")
    c.add_argument("--cloud", choices=SUPPORTED_CLOUDS)
    c.add_argument("--az-count", dest="az_count", type=int)
    c.add_argument("--nat-mode", dest="nat_mode", choices=list(NAT_MODES))
    c.add_argument("--gb", type=float, help="Estimated monthly egress GB through NAT")
    c.set_defaults(func=cmd_cost)

    ia = sub.add_parser(
        "init-answers",
        help="Write an answers YAML (sample template, or interactive Q&A only)",
    )
    ia.add_argument("--out", "-o", default="answers.yaml", help="Output path (default: answers.yaml)")
    ia.add_argument("--force", "-f", action="store_true", help="Overwrite existing file")
    ia.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run the Q&A wizard and write only the answers file (no Terraform project)",
    )
    ia.set_defaults(func=cmd_init_answers)

    ver = sub.add_parser("version", help="Show version")
    ver.set_defaults(func=cmd_version)

    return parser


_KNOWN_COMMANDS = (
    "generate",
    "validate",
    "bootstrap",
    "doctor",
    "import",
    "schema",
    "regions",
    "blueprints",
    "blueprint",
    "cost",
    "init-answers",
    "version",
    "help",
)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if not argv or (
        argv
        and not argv[0].startswith("-")
        and argv[0] not in _KNOWN_COMMANDS
    ):
        if not argv or argv[0].startswith("-"):
            argv = ["generate", *argv]

    args = parser.parse_args(argv)

    if getattr(args, "version", False) and not getattr(args, "command", None):
        return cmd_version(args)

    if not getattr(args, "func", None):
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except KeyboardInterrupt:
        _print()
        _err("Cancelled (Ctrl+C). No changes were required beyond what already completed.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
