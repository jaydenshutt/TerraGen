# Hub-and-spoke

Blueprint **`hub-spoke`** creates a **hub** network plus **N spoke** networks with connectivity between them.

## Generate

```bash
python -m terragen generate -a examples/answers-hub-spoke.yaml -o ./hub --force
```

Answers sketch:

```yaml
blueprint: hub-spoke
cloud: aws
hub_cidr: 10.0.0.0/16
spoke_count: 2
# optional: spoke_cidrs: ["10.1.0.0/16", "10.2.0.0/16"]
hub_spoke_connectivity: tgw    # aws: tgw | peering
az_count: 2
nat_mode: single
```

## Connectivity by cloud

| Cloud | Default | Alternative |
|-------|---------|-------------|
| AWS | **Transit Gateway** (`tgw`) | VPC peering (`peering`) |
| GCP | VPC peering | - |
| Azure | VNet peering | - |

## Mental model

- **Hub** = main TerraGen VPC/VNet (public/private subnets, optional NAT)  
- **Spokes** = additional VPCs/VNets with private subnets  
- Routes allow spoke ↔ hub (and often spoke default via hub TGW on AWS)

## Cost

- **AWS TGW** has hourly attachment and data processing charges.  
- Use `hub_spoke_connectivity: peering` for cheaper labs (limited transitive routing).

## After apply

- Place shared services (ingress, DNS, inspection) in the hub.  
- Place apps/data in spokes.  
- Review route tables in every AZ (TerraGen attaches hub→spoke routes on private RTs).
