# Cloud credentials

TerraGen does **not** store cloud passwords or API keys. It generates Terraform (and optionally calls **read-only** AWS APIs for live import).  
Authentication is the same system Terraform and the cloud CLIs already use.

**Disclaimer:** credentials grant access to real accounts. Use least privilege where you can, prefer non-prod for experiments, and review plans before apply. See [README — Disclaimer](../README.md#disclaimer).

---

## When do you need credentials?

| What you are doing | Cloud credentials required? |
|--------------------|-------------------------------|
| `terragen generate` / `init-answers` / `validate` / `schema` / `blueprints` / `cost` | **No** — local only |
| `terragen doctor` | **No** (only checks if CLIs exist) |
| `terraform init -backend=false` + `validate` | **No** |
| `terraform plan` / `apply` on a generated project | **Yes** for that cloud |
| `terragen bootstrap` (creates state bucket/table) | **Yes** |
| `terragen import --inventory …` | **No** |
| `terragen import --cloud aws --vpc-id …` (live) | **Yes** (AWS + `boto3`) |
| GitHub Actions with generated OIDC workflow | **CI role secrets**, not your laptop keys |

**Rule of thumb:** generate anytime; authenticate when you talk to a real cloud (plan, apply, bootstrap, live import).

---

## Mental model

```
You (CLI / env / SSO)
        │
        ├── terragen generate     → no cloud API
        ├── terragen import live  → AWS API (read-only describes)
        └── terraform / tofu      → AWS / GCP / Azure provider plugins
                 │
                 └── uses default credential chain for that provider
```

TerraGen does not pass credentials on the command line. Configure them the usual way for each cloud, then run Terraform in the generated folder.

---

## AWS

### What uses AWS auth

- `terraform plan|apply` for AWS networks, EKS, hub-spoke, bootstrap S3/DynamoDB, OIDC stack  
- `python -m terragen import --cloud aws --vpc-id …` (via **boto3**, same credential chain as the AWS SDK)

### Option A — AWS CLI profile (common)

```bash
# One-time or when rotating keys
aws configure
# or named profile:
aws configure --profile my-dev

export AWS_PROFILE=my-dev          # Linux / macOS
# PowerShell:
# $env:AWS_PROFILE = "my-dev"

aws sts get-caller-identity        # confirm who you are
```

### Option B — Environment variables

```bash
export AWS_ACCESS_KEY_ID=…
export AWS_SECRET_ACCESS_KEY=…
export AWS_SESSION_TOKEN=…          # if using temporary creds
export AWS_DEFAULT_REGION=us-east-1
```

Never commit these. Prefer SSO or a profile over long-lived keys in shell history.

### Option C — AWS IAM Identity Center (SSO)

```bash
aws configure sso
aws sso login --profile my-sso
export AWS_PROFILE=my-sso
aws sts get-caller-identity
```

### Live import extras

```bash
python -m pip install boto3        # required for live discovery
python -m terragen import --cloud aws --vpc-id vpc-xxx --region us-west-2 --dry-run
```

- Region must match the VPC’s region.  
- Identity needs **read** permissions on EC2 VPC APIs (`Describe*`). Import **generate** does not modify the account; `terraform apply` later **will** bind state (review carefully).  
- No AWS CLI on PATH is OK if **boto3** can still resolve credentials (shared `~/.aws` or env vars).

### Rough permissions (starting point)

| Task | Typical need |
|------|----------------|
| Network apply | EC2 VPC/subnet/NAT/SG (and related) create/update |
| Bootstrap | S3 + DynamoDB create |
| EKS blueprint | EKS + IAM + EC2 |
| Live import only | EC2 describe on VPC-related resources |

Lock down with least privilege for production; lab accounts often use a broad admin role.

---

## Google Cloud (GCP)

### What uses GCP auth

- Terraform Google provider for VPC, GKE, hub-spoke, bootstrap GCS bucket, OIDC stack  

### Application Default Credentials (recommended for local Terraform)

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

In answers / generate:

```yaml
cloud: gcp
region: us-central1
gcp_project_id: your-real-billing-project-id
```

If `gcp_project_id` is empty, TerraGen falls back to the **project slug** (often wrong for GCP). Always set the real project ID.

### Environment alternatives

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json   # CI/service account
export GOOGLE_CLOUD_PROJECT=your-project-id
# or CLOUDSDK_CORE_PROJECT
```

Prefer ADC or workload identity over downloading user keys when you can.

### APIs

Enable what you will apply (examples):

```bash
gcloud services enable compute.googleapis.com
# for GKE blueprints:
gcloud services enable container.googleapis.com
```

### Rough permissions

Compute Admin (or custom VPC roles) for networks; broader roles for GKE; storage admin for bootstrap bucket. Use a non-prod project first.

---

## Microsoft Azure

### What uses Azure auth

- Terraform `azurerm` for VNet, AKS, hub-spoke, bootstrap storage, related resources  

### Azure CLI (typical local path)

```bash
az login
az account show
az account list -o table
az account set --subscription "YOUR_SUBSCRIPTION_NAME_OR_ID"
```

Optional in answers:

```yaml
cloud: azure
region: eastus
azure_subscription_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

Providers also honor:

```bash
export ARM_SUBSCRIPTION_ID=…
export ARM_TENANT_ID=…
export ARM_CLIENT_ID=…             # service principal
export ARM_CLIENT_SECRET=…
```

### Rough permissions

Contributor (or custom) on the subscription/resource group for network stacks; AKS needs additional roles. Bootstrap creates a resource group + storage account for state.

---

## Local laptop vs GitHub Actions (OIDC)

| Context | How auth works |
|---------|----------------|
| **Your machine** | AWS profile / SSO / ADC / `az login` (this guide) |
| **Generated CI** | Workflow assumes a cloud role via **OIDC** — no long-lived access keys in GitHub if you wire it correctly |

OIDC is optional packaging under `oidc/` + `.github/workflows/terraform.yml`:

1. Apply `oidc/` once with privileged credentials on your machine.  
2. Put outputs into GitHub secrets (e.g. `AWS_ROLE_ARN`, GCP WIF, Azure client/tenant/subscription).  
3. CI uses federated login; your laptop credentials are not required in Actions.

See generated `oidc/README.md` and [bootstrap / remote state](bootstrap-and-state.md). OIDC does **not** replace local login for interactive `terraform apply`.

---

## OpenTofu

Same credential chains as Terraform. Use `tofu` instead of `terraform`, or:

```bash
python -m terragen bootstrap --project-dir . --binary tofu
```

---

## Windows notes

- Prefer `python -m terragen …` if `terragen` is not on PATH.  
- Cloud CLIs may be installed but missing from PATH; Terraform still works if SDK env/files are present (e.g. `%UserProfile%\.aws`).  
- PowerShell env examples:

```powershell
$env:AWS_PROFILE = "my-dev"
$env:AWS_DEFAULT_REGION = "us-west-2"
$env:ARM_SUBSCRIPTION_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

---

## Quick verification checklist

```bash
python -m terragen doctor          # Terraform + optional CLIs present?

# AWS
aws sts get-caller-identity        # or rely on boto3-only setup
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"

# GCP
gcloud auth application-default print-access-token > /dev/null
gcloud config get-value project

# Azure
az account show
```

Then in a generated project:

```bash
cd my-network          # or envs/dev if modular
terraform init -backend=false
terraform plan         # exercises real provider auth
```

---

## Common auth failures

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `NoCredentialsError` / Unable to locate credentials | Nothing in env or `~/.aws` | Configure profile/SSO or env vars |
| `AccessDenied` / 403 | Identity lacks permission | Elevate role or narrow the stack |
| Wrong AWS account | Wrong `AWS_PROFILE` | `aws sts get-caller-identity` |
| GCP resources in wrong project | Missing `gcp_project_id` | Set real project in answers |
| Azure subscription errors | Wrong account selected | `az account set --subscription …` |
| Live import fails, plan works | boto3 missing or different region | `pip install boto3`; match `--region` to VPC |
| CI plan fails, laptop works | OIDC secrets not set | Wire `oidc/` outputs into GitHub secrets |

More: [Troubleshooting](troubleshooting.md).

---

## Security hygiene

- Prefer **SSO / short-lived** credentials over permanent access keys.  
- Do **not** put secrets in answers YAML or commit `*.tfstate`, `.env`, or key JSON.  
- Generated `.gitignore` already ignores common state/secrets patterns — keep it.  
- Use separate cloud accounts or projects for experiments.  
- Review `terraform plan` every time; generators can still emit expensive or public resources depending on blueprint.

---

## Related docs

- [Getting started](getting-started.md)  
- [Brownfield import](brownfield-import.md)  
- [Remote state & bootstrap](bootstrap-and-state.md)  
- [CLI reference](cli-reference.md)  
- [Troubleshooting](troubleshooting.md)  
