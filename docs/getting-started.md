# Getting started

This walkthrough takes you from a clean machine to a Terraform plan for a cloud network.

## Prerequisites

- **Python 3.10+**
- **Terraform ≥ 1.5** (or OpenTofu 1.6+)
- Cloud credentials configured for the provider you choose (optional until `apply`):
  - AWS: `aws configure` or environment variables / SSO
  - GCP: `gcloud auth application-default login` + project
  - Azure: `az login`

## 1. Install TerraGen

```bash
git clone https://github.com/jaydenshutt/TerraGen.git
cd TerraGen
python -m pip install -e .
```

Verify:

```bash
python -m terragen version
python -m terragen doctor
```

> **Windows:** if `terragen` is not on your PATH, always use `python -m terragen …`.

## 2. Generate a project (pick one)

### Option A — Interactive wizard (best first time)

```bash
python -m terragen generate
```

TerraGen explains each question, shows a **summary**, and asks you to confirm before writing files.

**Answers only (no Terraform yet):**

```bash
python -m terragen init-answers --interactive --out answers.yaml
python -m terragen generate --answers answers.yaml --out ./my-network --force
```

### Option B — Example answers (fastest)

```bash
python -m terragen generate \
  --answers examples/answers-aws.yaml \
  --out ./my-network \
  --force
```

### Option C — Flags only

```bash
python -m terragen generate \
  --project my-app \
  --cloud aws \
  --region us-east-1 \
  --blueprint network \
  --out ./my-app-network \
  --force
```

Optional: run Terraform validate after generate (if Terraform is installed):

```bash
python -m terragen generate -a examples/answers-aws.yaml -o ./my-network --force --validate
```

## 3. Inspect the output

```bash
cd my-network   # or the path from --out / project name
ls
# expect: network.tf, variables.tf, providers.tf, backend.tf, bootstrap/, README.md, …
```

Read the **generated `README.md`** in that folder — it is tailored to your cloud and options.

## 4. (Recommended) Create remote state storage

Terraform cannot store state in a backend that does not exist yet. Use the bootstrap stack once:

```bash
cd bootstrap
terraform init
terraform plan
terraform apply
cd ..
```

Or from the parent:

```bash
python -m terragen bootstrap --project-dir . --dry-run
# when ready:
python -m terragen bootstrap --project-dir . --auto-approve
```

Details: [Remote state & bootstrap](bootstrap-and-state.md).

## 5. Initialize and plan the network

```bash
# With remote backend configured:
terraform init

# Local-only experiment (skip backend):
# terraform init -backend=false

terraform plan
```

Review the plan carefully (especially NAT gateways and public IPs — they cost money).

## 6. Apply (when ready)

```bash
terraform apply
```

## 7. Re-run / regenerate later

Your answers are saved as `terragen.answers.yaml`:

```bash
python -m terragen generate \
  --answers ./my-network/terragen.answers.yaml \
  --out ./my-network \
  --force
```

---

## Next steps

- Choose a richer [blueprint](blueprints.md) (private-only, EKS, hub-spoke, …)
- Use [modular layout](layouts.md) for multi-environment repos
- Wire [OIDC CI](cli-reference.md) from the generated `oidc/` folder
- Adopt an existing VPC: [Brownfield import](brownfield-import.md)

## Safety notes

- Generated stacks are **starters** — review IAM, CIDRs, and public exposure before production.
- `terraform destroy` deletes real cloud resources.
- Prefer non-production accounts for first experiments.
