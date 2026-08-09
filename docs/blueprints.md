# Blueprints

A **blueprint** is an opinionated preset. It sets defaults (NAT, endpoints, cluster flags, etc.). You can still override many fields in answers or flags.

List / describe:

```bash
python -m terragen blueprints
python -m terragen blueprint eks-cluster
```

## Network foundation

| ID | Intent |
|----|--------|
| `network` | Standard public + private subnets, optional single NAT |
| `network-ha` | Per-AZ NAT, flow logs, gateway endpoints, ≥2 AZs |
| `network-secure` | HA + tighter SSH defaults; GuardDuty on AWS |
| `network-private` | No public subnets / NAT; AWS interface endpoints pack |
| `network-3tier` | Public + private (app) + **isolated data** (no internet route) |

## Kubernetes — network only

| ID | Cloud | Intent |
|----|-------|--------|
| `eks-ready` | AWS | Tags + endpoints for future EKS (no cluster) |
| `gke-ready` | GCP | Secondary ranges for pods/services (no cluster) |
| `aks-ready` | Azure | NSGs + tags for AKS (no cluster) |

## Kubernetes — full cluster

| ID | Cloud | Creates |
|----|-------|---------|
| `eks-cluster` | AWS | EKS control plane + managed node group + IAM |
| `gke-cluster` | GCP | GKE Standard + node pool (VPC-native) |
| `aks-cluster` | Azure | AKS + system node pool |

See [Clusters](clusters.md) for deploy notes and cost warnings.

## Topology

| ID | Intent |
|----|--------|
| `hub-spoke` | Hub VPC/VNet + N spokes (AWS TGW or peering; GCP/Azure peering) |

See [Hub-and-spoke](hub-spoke.md).

## Choosing quickly

| Goal | Blueprint |
|------|-----------|
| First experiment | `network` |
| Production-ish app net | `network-ha` or `network-secure` |
| No public edge | `network-private` |
| Classic web/app/db | `network-3tier` |
| Run Kubernetes soon | `eks-cluster` / `gke-cluster` / `aks-cluster` |
| Multi-team isolation | `hub-spoke` |

## Example

```bash
python -m terragen generate \
  --project shop \
  --cloud aws \
  --blueprint network-ha \
  --out ./shop-net \
  --force
```
