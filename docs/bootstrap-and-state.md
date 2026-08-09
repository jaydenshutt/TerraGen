# Remote state and bootstrap

## Why bootstrap exists

Remote backends (S3, GCS, Azure Storage) must **exist before** Terraform can store state there. TerraGen therefore emits:

1. **`backend.tf`** — backend configuration for the main stack  
2. **`bootstrap/`** — a separate tiny stack that creates the bucket/table/account  

## Typical flow

Bootstrap **apply** needs cloud credentials for the target provider
([Cloud credentials](cloud-credentials.md)). Generate itself does not.

```bash
# 1. Generate with backend + bootstrap enabled (default)
python -m terragen generate -a answers.yaml -o ./net --force

# 2. Create state storage (local state for bootstrap itself)
cd net/bootstrap
terraform init
terraform apply
cd ..

# 3. Init main stack against remote backend
terraform init
# or: terraform init -migrate-state
terraform plan
```

## CLI helper

```bash
python -m terragen bootstrap --project-dir ./net --dry-run
python -m terragen bootstrap --project-dir ./net --auto-approve
```

Uses `terraform` by default; pass `--binary tofu` for OpenTofu.

## What gets created

| Cloud | Bootstrap resources |
|-------|---------------------|
| AWS | S3 state bucket (versioned, encrypted, public blocked) + DynamoDB lock table |
| GCP | GCS bucket (versioned) |
| Azure | Resource group + storage account + `tfstate` container |

Names are derived from `project` + `environment` (see generated `backend.tf`).

## Local-only mode

Skip remote state:

```yaml
enable_backend: false
enable_bootstrap: false
```

Or:

```bash
python -m terragen generate ... --no-backend
terraform init -backend=false
```

## Teardown order

1. Destroy **main** network/cluster stack first  
2. Then destroy **bootstrap** (state bucket)  

Never delete the state bucket while the main stack still needs it.
