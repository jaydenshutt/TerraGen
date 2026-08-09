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
