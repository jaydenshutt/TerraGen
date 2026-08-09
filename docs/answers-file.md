# Answers files

Answers files drive **non-interactive**, repeatable generation - ideal for CI and shared team defaults.

## Formats

- **YAML** (recommended): `answers.yaml`
- **JSON**: `answers.json`

```bash
python -m terragen generate --answers examples/answers-aws.yaml --out ./out --force
python -m terragen validate --answers examples/answers-aws.yaml
```

### Static sample template

```bash
python -m terragen init-answers --out answers.yaml
python -m terragen init-answers --out answers.yaml --force   # overwrite
```

### From the Q&A wizard only (no Terraform project)

```bash
python -m terragen init-answers --interactive --out answers.yaml
# short form:
python -m terragen init-answers -i -o answers.yaml --force
```

This runs the guided questions, shows a summary, then writes **only** the answers YAML.
Generate Terraform later:

```bash
python -m terragen validate --answers answers.yaml
python -m terragen generate --answers answers.yaml --out ./my-network --force
```

### Snapshot after a full interactive generate

`python -m terragen generate` (interactive) also writes `terragen.answers.yaml` inside the project folder - a full snapshot of the Q&A for regeneration.

JSON Schema (for editors):

```bash
python -m terragen schema -o answers.schema.json
# also shipped as schemas/answers.schema.json
```

## Minimal example

```yaml
project: my-app
cloud: aws
region: us-east-1
environment: dev
blueprint: network
vpc_cidr: 10.0.0.0/16
az_count: 2
nat_mode: single
```

## Common fields

| Field | Meaning |
|-------|---------|
| `project` | Name slug (lowercase, hyphens) |
| `cloud` | `aws` \| `gcp` \| `azure` |
| `region` | Cloud region / Azure location |
| `environment` | e.g. `dev`, `staging`, `prod` |
| `blueprint` | See [blueprints](blueprints.md) |
| `layout` | `flat` \| `modular` |
| `environments` | List of env roots when modular |
| `vpc_cidr` | Primary IPv4 range |
| `az_count` | 1-6 |
| `nat_mode` | `none` \| `single` \| `per_az` |
| `private_only` | Shorthand: no NAT, private-focused (AWS endpoints) |
| `enable_ipv6` | Dual-stack networking |
| `enable_flow_logs` | Flow logs |
| `enable_vpc_endpoints` | Gateway endpoints (S3/DynamoDB on AWS) |
| `enable_interface_endpoints` | AWS interface endpoints pack |
| `enable_backend` / `enable_bootstrap` | Remote state files |
| `generate_ci` / `generate_policies` / `generate_oidc` | Packaging extras |
| `github_org` / `github_repo` | OIDC subject |
| `gcp_project_id` | Required for real GCP deploys |
| `hub_cidr` / `spoke_count` / `hub_spoke_connectivity` | Hub-spoke |
| `cluster_name` / `cluster_version` / `node_*` | Cluster blueprints |

## Examples in the repo

| File | Use case |
|------|----------|
| `examples/answers-aws.yaml` | Basic AWS network |
| `examples/answers-gcp.yaml` | GCP VPC + NAT |
| `examples/answers-azure.yaml` | Azure VNet |
| `examples/answers-private-only.yaml` | Private AWS |
| `examples/answers-3tier.yaml` | Public / app / data tiers |
| `examples/answers-modular.yaml` | Multi-env modular |
| `examples/answers-eks-cluster.yaml` | Full EKS |
| `examples/answers-gke-cluster.yaml` | Full GKE |
| `examples/answers-aks-cluster.yaml` | Full AKS |
| `examples/answers-hub-spoke.yaml` | Hub + spokes |
| `examples/answers-ipv6.yaml` | Dual-stack |
| `examples/inventory-aws-sample.json` | Brownfield import inventory (AWS) |
| `examples/inventory-gcp-sample.json` | Brownfield import inventory (GCP, offline) |
| `examples/inventory-azure-sample.json` | Brownfield import inventory (Azure, offline) |

## CLI overrides

Flags override the answers file when both are set:

```bash
python -m terragen generate -a answers.yaml --region eu-west-1 --blueprint network-ha --force
```

## After generate

TerraGen writes **`terragen.answers.yaml`** into the output directory as a snapshot for regeneration.
