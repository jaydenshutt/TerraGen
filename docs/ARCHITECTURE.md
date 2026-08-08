# TerraGen architecture

## Generator pipeline

```
answers (CLI / interactive / YAML|JSON)
        │
        ▼
 TerraGenConfig  ──► validate ──► (errors stop)
        │
        ├── CIDR planner (public/private per AZ)
        ├── blueprint defaults (HA / secure)
        ├── tags / naming
        └── cost estimate
        │
        ▼
 Jinja2 render (common + cloud + bootstrap + policies + cicd)
        │
        ▼
 Output directory (.terragen-generated marker, answers snapshot, manifest)
```

## Design principles

1. **Correct HCL first** — every template must render valid Terraform for its cloud.
2. **Parity, not lowest common denominator** — use native constructs (SG vs firewall vs NSG).
3. **Safe defaults** — deny-by-default ingress; open management access is opt-in.
4. **Explicit cost knobs** — NAT mode is a first-class choice with estimates.
5. **Bootstrap remote state** — never assume the state bucket already exists.
6. **Regenerable** — answers snapshot + force overwrite of marked projects.

## Module map

| Module | Responsibility |
|--------|----------------|
| `config.py` | Dataclass model, blueprint layering, template context |
| `validate.py` | Errors vs warnings |
| `cidrs.py` | Subnet math |
| `regions.py` | Region catalog + NAT cost hints |
| `blueprints.py` | Catalog metadata |
| `cost.py` | Human-readable cost report |
| `render.py` | File plan + Jinja environment |
| `cli.py` | argparse UX |

## Template layout

```
templates/
  common/          # versions, providers, variables, outputs, README, backend…
  aws|gcp|azure/   # network, security, observability
  bootstrap/       # one-shot state backend per cloud
  policies/        # checkov, tflint
  cicd/            # GitHub Actions, GitLab CI
```

## Layout modes

| Mode | Output |
|------|--------|
| `flat` | Single root (`network.tf`, `providers.tf`, …) |
| `modular` | `modules/network` + `envs/<env>/*` thin roots + shared `bootstrap/` / `oidc/` |

## Private-only (AWS)

`private_only: true` or `--private-only` sets `nat_mode=none`, skips public subnets/IGW,
enables gateway + interface VPC endpoints (SSM, ECR, logs, STS, KMS, Secrets Manager, …).

## CLI surface (2.1+)

| Command | Role |
|---------|------|
| `generate` | Render project |
| `bootstrap` | Apply remote state backend stack |
| `doctor` | Local environment checks |
| `schema` | JSON Schema for answers |

## Extension points

- New blueprint: add to `SUPPORTED_BLUEPRINTS` + defaults in `config._apply_blueprint_defaults`
- New cloud: add region catalog, templates, bootstrap, oidc, outputs branches, tests
- New overlay (e.g. EKS): add template set + blueprint or `--addon` flag in a future release
