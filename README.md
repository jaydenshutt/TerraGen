# TerraGen

**World-class multi-cloud Terraform network generator** for AWS, Google Cloud, and Azure.

TerraGen asks a few questions (or reads a YAML/JSON answers file) and emits a production-minded Terraform project: multi-AZ public/private networking, optional NAT strategies, remote-state bootstrap, security baselines, flow logs, CI stubs, and policy-as-code starters.

[![CI](https://github.com/jaydenshutt/TerraGen/actions/workflows/ci.yml/badge.svg)](https://github.com/jaydenshutt/TerraGen/actions/workflows/ci.yml)

Created by [Jayden Shutt](https://www.linkedin.com/in/jaydenshutt/)

## Documentation

**Full walkthroughs live in [`docs/`](docs/README.md)** — getting started, interactive mode, answers files, blueprints, layouts, remote state, brownfield import, clusters, hub-spoke, CLI reference, and troubleshooting.

| Start here | |
|------------|--|
| [Getting started](docs/getting-started.md) | Install → generate → plan |
| [Cloud credentials](docs/cloud-credentials.md) | AWS / GCP / Azure auth (local + CI OIDC) |
| [Docs index](docs/README.md) | All guides |
| [CLI reference](docs/cli-reference.md) | Commands and flags |
| [Brownfield import](docs/brownfield-import.md) | Existing networks → Terraform (AWS live + multi-cloud inventory) |

---

## Why TerraGen?

| Problem | TerraGen |
|---------|----------|
| Boilerplate VPC modules differ per cloud | One CLI, three providers, consistent layout |
| Remote state is a chicken-and-egg problem | Optional **bootstrap** stack for the state backend |
| Generators emit insecure SSH from anywhere | Deny-by-default SGs/NSGs; bastion is opt-in with CIDRs |
| Cost surprises from per-AZ NAT | Explicit `nat_mode`: `none` / `single` / `per_az` + cost hints |
| No path to production | Flow logs, endpoints, GuardDuty, CI, Checkov/TFLint stubs |

---

## Features

- **Multi-cloud**: AWS, GCP, Azure with real resource parity (not stubs)
- **Layouts**: `flat` (single root) or `modular` (`modules/network` + `envs/{dev,prod}`)
- **Blueprints**: foundation networks, private/3-tier, K8s-ready, **full EKS/GKE/AKS clusters**, **hub-and-spoke**
- **IPv6 dual-stack**: optional dual-stack VPC/subnets (AWS/GCP/Azure)
- **Brownfield import**: AWS live VPC discovery **or** inventory JSON for **AWS / GCP / Azure** (no GCP/Azure account required to generate)
- **Private-only**: no NAT/public subnets + AWS interface endpoint pack (SSM, ECR, logs, …)
- **Interactive & non-interactive**: prompts or `--answers` JSON/YAML
- **Smart CIDR planning**: auto public/private subnets per AZ (or bring your own)
- **NAT strategies**: none, single, or per-AZ with rough monthly cost estimates
- **Security baselines**: app SG / firewall / NSG defaults; optional bastion rules
- **Observability**: VPC flow logs; AWS GuardDuty & billing alarm scaffolding
- **Remote state**: `backend.tf` + `terragen bootstrap` for the state backend
- **OIDC CI**: generated `oidc/` stack + GitHub Actions recipes (no long-lived keys)
- **Policy ready**: Checkov + TFLint starter configs
- **Tooling**: `doctor`, `schema`, JSON Schema for IDE validation
- **Regenerable**: `terragen.answers.yaml` + manifest for safe re-runs

---

## 5-minute quickstart

**Easiest install (no clone required):**

```bash
python -m pip install "git+https://github.com/jaydenshutt/TerraGen.git"
python -m terragen version          # TerraGen x.y.z — Created by Jayden Shutt
python -m terragen generate         # interactive wizard
```

**From a clone (dev / examples):**

```bash
git clone https://github.com/jaydenshutt/TerraGen.git
cd TerraGen
python -m pip install -e ".[dev]"
python -m terragen generate          # interactive — explains each question
# follow prompts, confirm the summary, then:
cd my-cloud-project-dev-terraform    # or whatever --out / project name you used
terraform init -backend=false
terraform validate
terraform plan
```

Prefer non-interactive?

```bash
python -m terragen generate -a examples/answers-aws.yaml -o ./my-network --force --validate
```

> **Windows tip:** if `terragen` is not on PATH, always use `python -m terragen …`.

**Credentials:** `generate` is local-only. Configure AWS / GCP / Azure before `terraform plan` / `apply`, bootstrap, or live import — see **[Cloud credentials](docs/cloud-credentials.md)**.

**Generated file layout:** HashiCorp-aligned `main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`, `terraform.tf` (+ domain files like `security.tf` for large stacks). See [Layouts](docs/layouts.md).

---

## Install

```bash
# Recommended for end users (GitHub, no manual clone)
python -m pip install "git+https://github.com/jaydenshutt/TerraGen.git"

# From a local clone (contributors / running examples)
git clone https://github.com/jaydenshutt/TerraGen.git
cd TerraGen
python -m pip install -e ".[dev]"

# Without packaging: deps only
python -m pip install -r requirements.txt
python -m terragen --help
```

Requires **Python 3.10+**. Generated projects target **Terraform ≥ 1.5** (OpenTofu 1.6+ works).

---

## Quick start (interactive)

```bash
python -m terragen generate
# or: terragen generate
# or: python TerraGen.py
```

### Non-interactive

```bash
terragen generate --answers examples/answers-aws.yaml --out ./my-network
cd my-network
# Bootstrap remote state (recommended)
cd bootstrap && terraform init && terraform apply && cd ..
terraform init
terraform plan
terraform apply
```

### Flags

```bash
terragen generate \
  --project my-app \
  --cloud aws \
  --region us-east-1 \
  --environment prod \
  --blueprint network-secure \
  --nat-mode per_az \
  --az-count 3 \
  --out ./my-app-prod \
  --force
```

---

## CLI reference

| Command | Description |
|---------|-------------|
| `terragen generate` | Generate a Terraform project (default) |
| `terragen bootstrap` | Create remote state backend (`terraform apply` in `bootstrap/`) |
| `terragen validate -a answers.yaml` | Validate an answers file |
| `terragen doctor` | Check Python deps, templates, Terraform, cloud CLIs |
| `terragen import` | Brownfield: discover VPC → Terraform import project |
| `terragen schema` | Print/write JSON Schema for answers files |
| `terragen regions aws\|gcp\|azure` | List curated regions |
| `terragen blueprints` | List blueprints |
| `terragen blueprint network-ha` | Describe a blueprint |
| `terragen cost --cloud aws --nat-mode per_az` | Estimate NAT-related monthly cost |
| `terragen init-answers` | Write a sample `answers.yaml` |
| `terragen version` | Show version |

Common `generate` options: `--answers`, `--out`, `--force`, `--dry-run`, `--layout modular`, `--environments dev,prod`, `--private-only`, `--interface-endpoints`, `--no-backend`, `--no-ci`, `--no-oidc`.

---

## Blueprints

| ID | Intent |
|----|--------|
| `network` | Foundation VPC/VNet, optional single NAT, flow logs |
| `network-ha` | Per-AZ NAT, flow logs, gateway endpoints, ≥2 AZs |
| `network-secure` | HA + GuardDuty (AWS), tighter SSH defaults, policy stubs |
| `network-private` | No public subnets / NAT; AWS interface endpoints pack |
| `network-3tier` | Public + private (app) + **isolated data** subnets (no internet route) |
| `eks-ready` | AWS HA + ELB subnet tags + ECR/SSM endpoints (network only) |
| `gke-ready` | GCP + secondary ranges for pods/services + Cloud NAT |
| `aks-ready` | Azure HA VNet + NSGs + AKS-oriented tags |
| `eks-cluster` | **Full Amazon EKS** control plane + managed node group |
| `gke-cluster` | **Full GKE** Standard cluster + node pool (VPC-native) |
| `aks-cluster` | **Full AKS** cluster + system node pool |
| `hub-spoke` | Hub VPC/VNet + N spokes (AWS TGW or peering; GCP/Azure peering) |

### IPv6 dual-stack

```bash
python -m terragen generate --cloud aws --blueprint network-ha --ipv6 --project dual --out ./dual --force
# or answers: enable_ipv6: true
```

### Brownfield import (existing networks)

| Path | Clouds |
|------|--------|
| **Inventory JSON** (offline) | AWS, **GCP**, **Azure** — no account needed to generate/validate |
| **Live discovery** | AWS only (`boto3`, read-only) |

```bash
# Multi-cloud inventory (works without GCP/Azure accounts)
python -m terragen import --inventory examples/inventory-gcp-sample.json -o ./imported-gcp
python -m terragen import --inventory examples/inventory-azure-sample.json -o ./imported-azure
python -m terragen import --inventory examples/inventory-aws-sample.json -o ./imported-aws

# Live AWS discovery (needs AWS creds + boto3 — see docs/cloud-credentials.md)
python -m terragen import --cloud aws --vpc-id vpc-0abc123 --region us-east-1 -o ./imported

cd ./imported-gcp && terraform init -backend=false && terraform validate
```

Full inventory field reference: [docs/brownfield-import.md](docs/brownfield-import.md).

---

## Answers file schema

```yaml
project: my-app                 # required-ish (default my-cloud-project)
cloud: aws                      # aws | gcp | azure
region: us-east-1
environment: dev                # dev | staging | prod | shared
blueprint: network              # network | network-ha | network-secure

vpc_cidr: 10.0.0.0/16
az_count: 2
# optional overrides:
# public_subnets: ["10.0.0.0/24", "10.0.1.0/24"]
# private_subnets: ["10.0.10.0/24", "10.0.11.0/24"]

nat_mode: single                # none | single | per_az
enable_flow_logs: true
enable_vpc_endpoints: false
enable_bastion_sg: false
ssh_cidrs: ["10.0.0.0/8"]

enable_guardduty: false         # AWS
enable_billing_alerts: false
billing_thresholds: { low: 50, medium: 200, high: 500 }
alert_emails: []

enable_backend: true
enable_bootstrap: true
generate_ci: true
generate_policies: true

owner: platform-team
cost_center: eng
tags: { Team: platform }

# cloud-specific
gcp_project_id: ""              # GCP billing project
azure_subscription_id: ""
```

See `examples/` for full samples per cloud.

---

## Generated layout

HashiCorp-style names (`main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`, `terraform.tf`):

```
my-app-dev-terraform/
├── terraform.tf              # required_version + required_providers
├── providers.tf
├── variables.tf
├── outputs.tf
├── main.tf                   # core network (VPC/VNet, subnets, NAT, routes)
├── security.tf
├── observability.tf          # when flow logs / GuardDuty / billing enabled
├── terraform.tfvars
├── backend.tf
├── bootstrap/                # create state backend once
│   ├── main.tf
│   └── README.md
├── policy/
│   ├── checkov.yaml
│   └── .tflint.hcl
├── .github/workflows/terraform.yml
├── .gitlab-ci.yml
├── README.md
├── terragen.answers.yaml
├── terragen.manifest.json
└── .terragen-generated
```

---

## Architecture by cloud

### AWS
VPC, public/private subnets, IGW, NAT (0/1/N), route tables, optional S3/DynamoDB gateway endpoints, app + optional bastion SGs, flow logs, GuardDuty, billing alarms (us-east-1 provider alias).

### GCP
Custom-mode VPC, public/private subnets with Private Google Access on private, Cloud Router + Cloud NAT, internal allow + optional IAP SSH + deny-all firewalls.

### Azure
Resource group, VNet, public/private subnets, NAT Gateway(s) + Standard PIPs, NSG defaults (allow VNet / deny all inbound), optional bastion NSG.

---

## Layouts

### Flat (default)

Single root module — simplest for small projects.

### Modular (recommended for multi-env)

```bash
terragen generate -a examples/answers-modular.yaml --out ./infra --force
# produces:
#   modules/network/     # reusable module
#   envs/dev|staging|prod/
#   bootstrap/
#   oidc/
cd infra
terragen bootstrap --project-dir . --auto-approve   # when ready
cd envs/dev && terraform init && terraform plan
```

## Private-only (AWS)

```bash
terragen generate -a examples/answers-private-only.yaml --out ./private-net --force
# or: terragen generate --cloud aws --private-only --project my-app --out ./out --force
```

Creates private subnets only, gateway + interface endpoints (SSM, ECR, logs, STS, KMS, Secrets Manager, …), no NAT idle cost.

## Multi-environment pattern (flat)

```bash
terragen generate -a answers.yaml --environment dev     --out infra/dev     --force
terragen generate -a answers.yaml --environment prod    --out infra/prod    --force
```

Prefer **modular** layout when sharing one module across envs.

## Bootstrap + OIDC

```bash
terragen bootstrap --project-dir ./my-network --auto-approve
# then apply oidc/ once and set GitHub secrets from outputs
cd my-network/oidc && terraform apply
```

## OpenTofu

Generated code works with **OpenTofu 1.6+**. Replace `terraform` with `tofu` in the deploy steps.

## Development

```bash
pip install -e ".[dev]"
pytest -q
terragen generate --answers examples/answers-aws.yaml --out /tmp/tg --force
# optional if Terraform is installed:
cd /tmp/tg && terraform init -backend=false && terraform validate
```

---

## Roadmap ideas

- IPv6 dual-stack
- Shared VPC / hub-spoke blueprints
- EKS/GKE/AKS starter overlays
- Live AZ discovery via cloud APIs when credentials are present
- OpenTofu-first docs and providers lockfile generation

---

## Disclaimer

TerraGen is provided **as-is** under the [MIT License](LICENSE), **without warranty of any kind** (express or implied), including merchantability, fitness for a particular purpose, and noninfringement.

**You use this tool at your own risk.** Generated Terraform is a starting point only. Before you `plan` or `apply` in any account:

- Review every resource, IAM policy, network exposure, and cost implication
- Treat blueprints as accelerators—not certified production designs for your environment
- Brownfield import and discovery can be imperfect; expect drift and manual fixes

The authors and contributors accept **no responsibility** for cloud spend, outages, security incidents, data loss, compliance outcomes, or any other consequences of using TerraGen or the code it generates.

We still **hope TerraGen helps you accelerate** multi-cloud networking and infrastructure-as-code—so you can spend less time on boilerplate and more time on what you are building.

## License

MIT — see [LICENSE](LICENSE) for the full legal text (including the “AS IS” and limitation of liability clauses).
