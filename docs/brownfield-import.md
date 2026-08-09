# Brownfield import (existing AWS VPC)

Bring an **existing VPC** under Terraform using import blocks (Terraform ≥ 1.5).

This is **not** full-account import — it targets the **VPC network surface**.

## Paths

### A) Live discovery (AWS)

Needs: **AWS credentials** (same chain as Terraform/boto3) + `boto3` (`pip install boto3`).  
Discovery is **read-only** (`Describe*`); it does not create resources.  
See **[Cloud credentials — AWS](cloud-credentials.md#aws)** (profiles, SSO, env vars, region).

```bash
# Confirm identity (optional)
# aws sts get-caller-identity
# or: python -c "import boto3; print(boto3.client('sts').get_caller_identity())"

python -m terragen import \
  --cloud aws \
  --vpc-id vpc-0123456789abcdef0 \
  --region us-east-1 \
  --out ./imported
```

Use the **region where the VPC lives**. Wrong region → not found / empty discovery.

### B) Inventory JSON (no live API)

```bash
python -m terragen import \
  --inventory examples/inventory-aws-sample.json \
  --out ./imported
```

### C) Dry-run discovery JSON

```bash
python -m terragen import --cloud aws --vpc-id vpc-xxx --region us-east-1 --dry-run
```

## What gets discovered (AWS deep)

| Resource | Notes |
|----------|--------|
| VPC | CIDR, DNS attributes, tags |
| Subnets | CIDR, AZ, map public IP, tags (named resources) |
| Internet gateway | |
| NAT gateways + Elastic IPs | |
| Route tables | Non-local routes |
| Route table associations | Subnet ↔ RT |
| Security groups | Ingress/egress rules |
| Network ACLs | Entries (skip max rule 32767) |
| VPC endpoints | Gateway + interface |

## Output layout

```
imported/
├── imports.tf       # import { to = … id = "…" }
├── vpc.tf
├── subnets.tf
├── gateways.tf      # IGW, EIP, NAT
├── routes.tf
├── security.tf
├── acls.tf
├── endpoints.tf
├── outputs.tf
├── versions.tf
├── discovered.json
└── README.md
```

## Adopt into state

```bash
cd imported
terraform init
terraform plan     # align remaining drift (tags, optional attrs)
# edit .tf files as needed
terraform apply    # runs import blocks into state
```

## Safety

- **Do not** `terraform destroy` until you understand blast radius.  
- Security groups with **self-references** may use `ignore_changes` on rules — refine by hand.  
- Default NACL associations may be sensitive; verify before apply.  
- Prefer a non-production VPC for your first import.  

## GCP / Azure

Live deep discovery is **AWS-first**. For other clouds, provide a compatible inventory JSON and re-run `--inventory`.

## Greenfield vs brownfield

| | Greenfield `generate` | Brownfield `import` |
|--|----------------------|---------------------|
| Goal | Create new design | Manage existing VPC |
| Input | Answers / wizard | VPC ID or inventory |
| Output | Full blueprint stack | Import blocks + matching resources |
