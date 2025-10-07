# TerraGen - A Cloud-Agnostic Terraform Generator

Created by [Jayden Shutt](https://www.linkedin.com/in/jaydenshutt/)

TerraGen is a Python-based tool that simplifies the creation of foundational network infrastructure in AWS, Google Cloud Platform (GCP), and Azure. It interactively prompts you for key configuration details and generates a ready-to-use Terraform project, allowing you to quickly provision a standardized network environment in the cloud of your choice.

## Features

- **Multi-Cloud Support**: Generates Terraform code for AWS, GCP, and Azure.
- **Interactive & Non-Interactive Modes**: Use the interactive prompts to guide you through the setup, or provide a JSON/YAML answers file for automated, repeatable deployments.
- **Standardized Network Architecture**: Creates a best-practice network setup, including:
  - A Virtual Private Cloud (VPC) / Virtual Network (VNet).
  - Public and private subnets distributed across multiple availability zones.
  - An Internet Gateway and NAT Gateways for secure and scalable internet access.
  - Default route tables for controlling traffic.
- **Remote State Configuration**: Automatically generates a backend configuration file to help you set up remote state management.

## How to Use

The generator can be run in two modes: interactive or non-interactive.

### Interactive Mode

To start the interactive setup, simply run the script:

```sh
python TerraGen.py
```

The script will ask you for the following information:
- **Project Name**: A unique name for your project.
- **Cloud Provider**: `aws`, `gcp`, or `azure`.
- **Region**: The cloud region where you want to deploy your infrastructure.
- **VPC CIDR Block**: The IP address range for your virtual network.
- **Number of Availability Zones**: The number of AZs to distribute your subnets across.

### Non-Interactive Mode

For automated runs, you can provide a JSON or YAML file containing the answers.

1.  Create an `answers.json` or `answers.yaml` file:

    **JSON Example:**
    ```json
    {
      "project": "my-automated-project",
      "cloud": "aws",
      "region": "us-east-1",
      "vpc_cidr": "10.10.0.0/16",
      "az_count": 2
    }
    ```

2.  Run the generator with the `--answers` flag:
    ```sh
    python TerraGen.py --answers answers.json
    ```

You can also specify an output directory for the generated files with the `--out` flag:

```sh
python TerraGen.py --answers answers.yaml --out ./my-terraform-project
```

## Generated Project Structure

After running the generator, a new directory will be created with the following structure:

```
my-terraform-project/
├── main.tf
├── variables.tf
├── outputs.tf
├── backend.tf
└── README.md
```

- `main.tf`: Contains the core infrastructure resources.
- `variables.tf`: Defines the input variables for your project.
- `outputs.tf`: Specifies the output values, such as VPC IDs and subnet IDs.
- `backend.tf`: Configures Terraform's remote state.
- `README.md`: Provides instructions on how to use the generated code.

## Next Steps

Once your Terraform project is generated, navigate into the output directory and follow the instructions in the generated `README.md` file to deploy your infrastructure:

1.  `cd my-terraform-project`
2.  `terraform init`
3.  `terraform plan`
4.  `terraform apply`

