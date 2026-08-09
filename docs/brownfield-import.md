# Brownfield import (existing networks)

Bring an **existing network** under Terraform using import blocks (Terraform ≥ 1.5).

This is **not** full-account import — it targets the **VPC / VPC Network / VNet surface**.

| Cloud | Inventory JSON (no account) | Live API discovery |
|-------|----------------------------:|--------------------|
| **AWS** | Yes (`inventory-aws-sample.json`) | Yes (boto3, read-only) |
| **GCP** | Yes (`inventory-gcp-sample.json`) | Not yet (inventory is the supported path) |
| **Azure** | Yes (`inventory-azure-sample.json`) | Not yet (inventory is the supported path) |

You **do not** need a GCP or Azure account to generate and `terraform validate` inventory-based import projects.

---

## Paths

### A) Inventory JSON (all clouds — recommended offline path)

```bash
# AWS
python -m terragen import --inventory examples/inventory-aws-sample.json -o ./imported-aws

# GCP (no GCP account required to generate)
python -m terragen import --inventory examples/inventory-gcp-sample.json -o ./imported-gcp

# Azure (no Azure subscription required to generate)
python -m terragen import --inventory examples/inventory-azure-sample.json -o ./imported-azure
```

Then:

```bash
cd ./imported-gcp   # or aws / azure
terraform init -backend=false
terraform validate
# terraform plan   # needs real credentials + real resource IDs for a useful plan
```

### B) Live discovery (AWS only)

Needs: **AWS credentials** + `boto3` (`pip install boto3`).  
Discovery is **read-only** (`Describe*`). See **[Cloud credentials — AWS](cloud-credentials.md#aws)**.

```bash
python -m terragen import \
  --cloud aws \
  --vpc-id vpc-0123456789abcdef0 \
  --region us-east-1 \
  --out ./imported
```

### C) Dry-run (print inventory JSON)

```bash
# Live AWS
python -m terragen import --cloud aws --vpc-id vpc-xxx --region us-east-1 --dry-run

# Or load inventory and print normalized form after a full generate dry path —
# use --inventory then inspect discovered.json in the output directory.
```

---

## Inventory schemas

### Common fields

| Field | Notes |
|-------|--------|
| `cloud` | `aws` \| `gcp` \| `azure` (**required**) |
| `region` / `location` | Region or Azure location |
| `subnets` | List of subnet objects (`id`, `name`, `cidr`, …) |
| `tags` / `labels` | Optional map |

### AWS (deep)

See `examples/inventory-aws-sample.json`. Supports VPC, subnets, IGW, NAT+EIP, route tables + associations, SGs, NACLs, VPC endpoints.

### GCP

| Field | Required | Notes |
|-------|----------|--------|
| `project_id` | **Yes** | GCP project owning the network |
| `network_name` or `vpc_id` | **Yes** | VPC network **name** |
| `routing_mode` | No | default `REGIONAL` |
| `auto_create_subnetworks` | No | default `false` |
| `subnets[]` | Recommended | `cidr`, `region`, `private_ip_google_access`, `secondary_ranges` |
| `routers[]` | No | Cloud Router; nested `nats[]` for Cloud NAT |
| `firewalls[]` | No | `direction`, `priority`, `source_ranges`, `allows` |

Import IDs use shapes like:

- Network: `projects/{project}/global/networks/{name}`  
- Subnet: `projects/{project}/regions/{region}/subnetworks/{name}`  

### Azure

| Field | Required | Notes |
|-------|----------|--------|
| `resource_group` | **Yes*** | Or embed in full VNet resource ID |
| `vpc_id` / `vpc_name` | **Yes** | Prefer full ARM resource ID for apply |
| `address_spaces` | Recommended | List; falls back to `vpc_cidr` |
| `subnets[]` | Recommended | `cidr` / `address_prefixes`; optional `nsg_id` |
| `network_security_groups[]` | No | Rules as `rules[]` |
| `route_tables[]` | No | Nested `routes[]` |
| `public_ips[]` | No | |
| `nat_gateways[]` | No | Optional `public_ip_id` for association |

\* If `vpc_id` is a full ARM ID containing `/resourceGroups/{name}/`, the RG is parsed automatically.

Sample IDs use a zero GUID subscription — **replace with real IDs before apply**.

---

## Output layout

### AWS

```
imported/
├── terraform.tf / providers.tf / main.tf / outputs.tf
├── imports.tf
├── subnets.tf / gateways.tf / routes.tf
├── security.tf / acls.tf / endpoints.tf
├── discovered.json / README.md
```

### GCP

```
imported/
├── terraform.tf / providers.tf / main.tf / outputs.tf
├── imports.tf
├── subnets.tf / routers.tf / firewalls.tf
├── discovered.json / README.md
```

### Azure

```
imported/
├── terraform.tf / providers.tf / main.tf / outputs.tf
├── imports.tf
├── subnets.tf / nsg.tf / routes.tf / public_ips.tf / nat.tf
├── discovered.json / README.md
```

---

## Adopt into state

```bash
cd imported
terraform init
terraform plan     # align drift (tags, optional attrs, real IDs)
# edit .tf as needed
terraform apply    # runs import blocks into state
```

## Safety

- **Do not** `terraform destroy` until you understand blast radius.  
- AWS SG self-references / default NACL associations may need hand-tuning.  
- GCP secondary ranges and NAT options often show plan drift.  
- Azure: fix subscription GUIDs and association import IDs before apply.  
- Prefer non-production networks for first import.  

## Building inventory without cloud console automation

1. Copy the matching `examples/inventory-*-sample.json`.  
2. Replace names, CIDRs, and IDs with values from your console / CLI dumps.  
3. `terragen import --inventory yours.json -o ./imported`  
4. `terraform validate` offline; plan only when credentials exist.

## Greenfield vs brownfield

| | Greenfield `generate` | Brownfield `import` |
|--|----------------------|---------------------|
| Goal | Create new design | Manage existing network |
| Input | Answers / wizard | Inventory JSON (or AWS VPC ID) |
| Output | Full blueprint stack | Import blocks + matching resources |
| GCP/Azure account for generate | Not required | **Not required** for inventory path |

## Related

- [Cloud credentials](cloud-credentials.md)  
- [CLI reference](cli-reference.md)  
- [Troubleshooting](troubleshooting.md)  
