# Managed Kubernetes clusters

Blueprints `eks-cluster`, `gke-cluster`, and `aks-cluster` generate **network + control plane + node pool** starters.

## Generate

```bash
# AWS EKS
python -m terragen generate -a examples/answers-eks-cluster.yaml -o ./eks --force

# GCP GKE
python -m terragen generate -a examples/answers-gke-cluster.yaml -o ./gke --force

# Azure AKS
python -m terragen generate -a examples/answers-aks-cluster.yaml -o ./aks --force
```

### Modular layout (recommended multi-env)

```bash
python -m terragen generate \
  -a examples/answers-eks-cluster.yaml \
  --layout modular --environments dev,prod \
  -o ./eks-mod --force
```

Produces:

```text
modules/network/   # VPC only
modules/cluster/   # EKS/GKE/AKS only
envs/dev/main.tf   # module "network" + module "cluster"
```

Cluster is **not** buried inside the network module. Env roots pass network outputs (VPC/subnet IDs) into the cluster module.

## What you get (high level)

### EKS (`eks-cluster`)
- HA VPC (per-AZ NAT, endpoints, subnet ELB tags)
- EKS cluster IAM roles
- Managed node group (min/desired/max)
- Cluster security group hooks

### GKE (`gke-cluster`)
- Custom VPC + Cloud NAT
- Secondary ranges for pods/services
- Regional GKE Standard cluster + node pool
- Workload Identity enabled

### AKS (`aks-cluster`)
- HA VNet + NAT + NSGs
- AKS with autoscaling system pool
- Azure CNI, system-assigned identity
- Network Contributor on the VNet

## Useful answers fields

```yaml
cluster_name: my-app-dev-k8s
cluster_version: "1.29"
node_instance_type: t3.medium   # or e2-medium / Standard_D2s_v3
node_desired_size: 2
node_min_size: 1
node_max_size: 4
cluster_private_endpoint: true  # provider-specific private options
```

## Deploy checklist

1. Bootstrap remote state ([guide](bootstrap-and-state.md))  
2. `terraform plan` - expect IAM + control plane + nodes (costly)  
3. Confirm K8s version is still supported in your region  
4. After apply: configure `kubectl` with cloud CLI  
5. Add cluster add-ons (CSI, ingress, etc.) outside this starter as needed  

## Network-only alternatives

If you only want the VPC prep without a cluster:

- `eks-ready` / `gke-ready` / `aks-ready`

## Cost warning

Control planes and node pools incur ongoing charges. Destroy when finished with labs.
