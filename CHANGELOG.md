# Changelog

## 3.0.1 — 2026-08-08

### Improved
- **Deep AWS brownfield import**: subnets (named), IGW, NAT+EIP, route tables + associations + routes,
  security groups (ingress/egress), network ACLs, VPC endpoints; multi-file HCL + counts in CLI
- Richer sample inventory; import tests; terraform-validate-clean generated import projects
- Hub-spoke multi-AZ private routes; AKS autoscaling pool without conflicting `node_count`; modular cluster outputs

## 3.0.0 — 2026-08-08

### Added
- **Real cluster blueprints**: `eks-cluster`, `gke-cluster`, `aks-cluster` (control plane + node pools)
- **Hub-and-spoke**: `hub-spoke` with AWS Transit Gateway (or peering) and GCP/Azure peering
- **IPv6 dual-stack**: `enable_ipv6` / `--ipv6` on VPC and subnets (AWS EIGW, GCP stack_type, Azure ULA)
- **Brownfield import**: `terragen import` for AWS live VPC discovery (boto3) or inventory JSON → import blocks
- Examples for clusters, hub-spoke, IPv6, and sample inventory

### Notes
- Cluster stacks are opinionated starters — review IAM, versions, and private API settings before production
- Hub-spoke TGW incurs AWS hourly cost; use `hub_spoke_connectivity: peering` for a cheaper lab

## 2.2.0 — 2026-08-08

### Added
- **Blueprints:** `network-private`, `network-3tier`, `eks-ready`, `gke-ready`, `aks-ready`
- Isolated/data-tier subnets (3-tier) across AWS/GCP/Azure
- GKE secondary pod/service ranges; EKS subnet role tags
- Interactive polish: progress counters, summary + confirm, Ctrl+C handling
- Friendlier validation messages (suggested project slugs, blueprint/cloud hints)
- `generate --validate` runs terraform/tofu fmt + validate when installed
- 5-minute quickstart in README; re-run command printed after generate

## 2.1.0 — 2026-08-08

### Added
- **Modular layout**: `layout: modular` → `modules/network` + `envs/{dev,prod}`
- **Private-only mode**: `private_only` / `--private-only` with AWS interface endpoint pack
- **`terragen bootstrap`**: generate + apply remote state backend
- **`terragen doctor`**: environment health checks
- **`terragen schema`**: JSON Schema for answers (also `schemas/answers.schema.json`)
- **OIDC stacks** under `oidc/` for GitHub Actions (AWS / GCP / Azure)
- CI matrix with real `terraform fmt` + `validate` per cloud profile

### Changed
- GitHub Actions workflow uses OIDC login steps and modular-aware working directory
- Cost report mentions private endpoints and modular apply path

## 2.0.0 — 2026-08-08

Complete rewrite into a production-minded multi-cloud generator.

### Breaking
- Package layout moved to `terragen/` with installable CLI (`terragen` / `python -m terragen`)
- Corrupted dual-version Jinja templates replaced with clean per-cloud templates
- Answers schema expanded (see README); legacy `enable_nat` still accepted

### Added
- Blueprints: `network`, `network-ha`, `network-secure`
- NAT modes: `none` | `single` | `per_az` with cost estimates
- Full AWS / GCP / Azure network parity (subnets, NAT, routing, security baselines)
- Remote state `backend.tf` + `bootstrap/` stacks per cloud
- Flow logs, VPC gateway endpoints (AWS), GuardDuty, billing alarm scaffolding
- CI stubs (GitHub Actions, GitLab CI) and policy stubs (Checkov, TFLint)
- CLI: `generate`, `validate`, `regions`, `blueprints`, `blueprint`, `cost`, `init-answers`
- Comprehensive pytest suite and example answers files
- Safer defaults (no open SSH by default)

### Fixed
- Templates that previously failed to render or emitted invalid HCL
- GCP Cloud NAT now targets private subnets correctly via dynamic blocks
- Input validation for project names, CIDRs, emails, cloud/blueprint choices

## 1.0.0 — initial public prototype

Interactive / non-interactive Terraform starter for AWS, GCP, Azure (broken templates in tree).
