# Layouts

TerraGen can write a **flat** project or a **modular** multi-environment tree.

## HashiCorp conventions (how we compare)

HashiCorp documents two closely related recommendations:

1. **[Standard module structure](https://developer.hashicorp.com/terraform/language/modules/develop/structure)** — reusable modules should have at least `main.tf`, `variables.tf`, `outputs.tf` (and usually `README.md`). For complex modules, resources may be **split across multiple `.tf` files**, but nested **module calls** should live in `main.tf`.
2. **[Style guide — file names](https://developer.hashicorp.com/terraform/language/style)** — common root layout:
   - `main.tf` — resources / data sources (or module calls)
   - `variables.tf` — input variables
   - `outputs.tf` — outputs
   - `providers.tf` — provider blocks
   - `terraform.tf` / versions — `required_version` / `required_providers` (TerraGen uses `versions.tf`)
   - `backend.tf` — backend configuration
   - `locals.tf` — optional locals
   - `terraform.tfvars` — variable values

Terraform itself only requires `*.tf` in a directory; filenames are **convention**, not a hard parser rule.

### Does TerraGen meet the standard?

| Convention | Flat layout | Modular layout |
|------------|-------------|----------------|
| `variables.tf` for inputs | **Yes** | **Yes** (`modules/network/variables.tf`) |
| `outputs.tf` for outputs | **Yes** | **Yes** (module + env `outputs.tf`) |
| `providers.tf` | **Yes** | **Yes** (`envs/<env>/providers.tf`) |
| Backend separate (`backend.tf`) | **Yes** (optional) | **Yes** per env |
| Version constraints | **Yes** (`versions.tf`) | **Yes** |
| `main.tf` as primary entry / module calls | **Partial** — resources live in **domain files** (`network.tf`, `security.tf`, `cluster.tf`, …), not a single `main.tf` | **Yes for env roots** — `envs/<env>/main.tf` holds `module "network" { ... }` |
| Module has `main.tf` + variables + outputs | N/A | **Partial** — module has `variables.tf` + `outputs.tf` + domain files (`network.tf`, …); no single `main.tf` name |
| Nested module calls only in `main.tf` | N/A | **Yes** — only env `main.tf` calls the network module |

**Summary:** TerraGen follows HashiCorp on **variables / outputs / providers / backend / versions**, and on **modular roots calling modules via `main.tf`**. Flat (and the shared network module) use **purpose-split resource files** (`network.tf`, `security.tf`, …), which HashiCorp allows for complex modules, but the **filename** is not always `main.tf`. That is intentional: multi-cloud network stacks are large; splitting by concern is easier to navigate than one giant `main.tf`.

Industry practice (AWS, Google, many module registries) also commonly uses `vpc.tf` / `security.tf`-style splits alongside `variables.tf` and `outputs.tf`.

```yaml
layout: flat      # default
# or
layout: modular
environments:
  - dev
  - staging
  - prod
```

```bash
python -m terragen generate -a answers.yaml --layout modular --environments dev,prod -o ./infra --force
```

## Flat (default)

```
my-project-dev-terraform/
├── network.tf
├── security.tf
├── variables.tf
├── providers.tf
├── backend.tf
├── bootstrap/
├── oidc/            # if enabled
├── .github/workflows/
└── README.md
```

**Best for:** single environment, demos, simple apps.

## Modular

```
infra/
├── modules/network/     # shared module (network + optional cluster/hub)
├── envs/
│   ├── dev/
│   │   ├── main.tf      # module "network" { ... }
│   │   ├── providers.tf
│   │   └── backend.tf
│   └── prod/
├── bootstrap/           # shared once
├── oidc/
└── README.md
```

**Best for:** same network design across environments with separate state keys.

Deploy:

```bash
cd infra/bootstrap && terraform apply && cd ../..
cd infra/envs/dev
terraform init
terraform plan
terraform apply
```

## Regenerating

Use `--force` on an existing TerraGen output (directory must contain `.terragen-generated` or be empty of foreign content).
