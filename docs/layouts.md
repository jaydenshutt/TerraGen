# Layouts

TerraGen can write a **flat** project or a **modular** multi-environment tree.

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

## HashiCorp standard (we match this)

TerraGen targets HashiCorp’s recommended names:

| File | Role |
|------|------|
| **`main.tf`** | Primary entry — core network resources **or** `module` calls |
| **`variables.tf`** | Input variables |
| **`outputs.tf`** | Outputs |
| **`providers.tf`** | Provider configuration |
| **`terraform.tf`** | `required_version` + `required_providers` |
| **`backend.tf`** | Remote state backend (optional) |
| **`terraform.tfvars`** | Default variable values |

References:

- [Standard module structure](https://developer.hashicorp.com/terraform/language/modules/develop/structure)
- [Style guide — file names](https://developer.hashicorp.com/terraform/language/style)

**Complex stacks:** HashiCorp allows splitting resources across additional `.tf` files. TerraGen keeps focused files such as `security.tf`, `cluster.tf`, `hub_spoke.tf`, and `observability.tf` next to `main.tf` so large multi-cloud projects stay readable. Nested **module** blocks always live in `main.tf` (modular env roots).

## Flat (default)

```
my-project-dev-terraform/
├── terraform.tf       # required_version / providers
├── providers.tf
├── variables.tf
├── outputs.tf
├── main.tf            # core VPC / VNet / subnets / NAT / routes
├── security.tf
├── observability.tf   # optional
├── cluster.tf         # optional
├── hub_spoke.tf       # optional
├── backend.tf         # optional
├── terraform.tfvars
├── bootstrap/
├── oidc/              # if enabled
├── .github/workflows/
└── README.md
```

**Best for:** single environment, demos, simple apps.

## Modular

```
infra/
├── modules/network/
│   ├── terraform.tf
│   ├── main.tf          # core network resources
│   ├── variables.tf
│   ├── outputs.tf
│   ├── security.tf
│   └── …                # cluster.tf / hub_spoke.tf when enabled
├── envs/
│   ├── dev/
│   │   ├── terraform.tf
│   │   ├── providers.tf
│   │   ├── main.tf      # module "network" { … }
│   │   ├── outputs.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   └── prod/
├── bootstrap/
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

**Note:** Older TerraGen versions used `network.tf` / `versions.tf`. From **3.0.3+** those map to **`main.tf`** / **`terraform.tf`**. Re-generate with `--force` (or rename files) when upgrading.
