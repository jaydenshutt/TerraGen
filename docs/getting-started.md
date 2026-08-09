# Getting started

This walkthrough takes you from a clean machine to a Terraform plan for a cloud network.

## Disclaimer (read before you apply)

TerraGen is provided **as-is**, **without warranty of any kind**. You use it **at your own risk**.

Generated projects can create real cloud resources that cost money and affect production if you apply them carelessly. Always review `terraform plan` (and security/IAM/network exposure) before apply. The authors take **no responsibility** for outcomes in your accounts.

We **do** hope this tool helps you accelerate solid multi-cloud networking and IaC setup. Full legal terms: [LICENSE](../LICENSE). Plain-language summary: [README — Disclaimer](../README.md#disclaimer).

## Prerequisites

- **Python 3.10+**
- **Terraform ≥ 1.5** (or OpenTofu 1.6+)
- **Cloud credentials** — **not** required for `generate`; **required** for `terraform plan` / `apply`, `bootstrap`, and live AWS `import`

| Cloud | Typical local login |
|-------|---------------------|
| AWS | `aws configure` / SSO profile, or env vars (`AWS_PROFILE`, …) |
| GCP | `gcloud auth application-default login` + real `gcp_project_id` |
| Azure | `az login` + correct subscription |

Full guide (when you need auth, env vars, SSO, OIDC CI, Windows): **[Cloud credentials](cloud-credentials.md)**.

## 1. Install TerraGen

### Option A — From GitHub (fastest for users)

```bash
python -m pip install "git+https://github.com/jaydenshutt/TerraGen.git"
```

No clone required. You still need Terraform installed separately for `plan` / `apply`.

### Option B — Clone (examples + development)

```bash
git clone https://github.com/jaydenshutt/TerraGen.git
cd TerraGen
python -m pip install -e .
# with tests: python -m pip install -e ".[dev]"
```

Verify:

```bash
python -m terragen version    # shows version + Created by Jayden Shutt
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
# expect: main.tf, variables.tf, outputs.tf, providers.tf, terraform.tf, backend.tf, bootstrap/, …
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

This step uses **your cloud credentials** (Terraform provider default chain). Confirm login first if needed: [Cloud credentials](cloud-credentials.md).

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

- [Cloud credentials](cloud-credentials.md) — AWS / GCP / Azure and CI OIDC
- Choose a richer [blueprint](blueprints.md) (private-only, EKS, hub-spoke, …)
- Use [modular layout](layouts.md) for multi-environment repos
- Wire [OIDC CI](cloud-credentials.md#local-laptop-vs-github-actions-oidc) from the generated `oidc/` folder
- Adopt an existing VPC: [Brownfield import](brownfield-import.md)

## Safety notes

- Generated stacks are **starters** — review IAM, CIDRs, and public exposure before production.
- `terraform destroy` deletes real cloud resources.
- Prefer non-production accounts for first experiments.
