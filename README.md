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

Non-interactive (useful for CI or tests):

    python TerraGen.py --answers sample_answers.json --out ./my-terraform

Advanced options
----------------
- `--modules` — generate a `modules/vpc` Terraform module and have the root call it. Helpful to teach module structure.
- `--create-backend` — attempt to create an S3 bucket `PROJECT-tfstate` and a DynamoDB table for state locking. Requires AWS credentials and permissions. Use with `--yes` to skip confirmation.
- `--fmt-validate` — run `terraform fmt -recursive` and `terraform validate` in the generated folder (requires terraform installed locally).

Then:

    cd my-terraform
    terraform init
    terraform plan -out plan.tf
    terraform apply "plan.tf"

Notes and next steps
--------------------
- The generator is intentionally simple and educational. Security group rules are permissive for clarity — tighten them before using in production.
- If you enable the S3 backend option, create the S3 bucket and give your IAM principal permissions to access it before running `terraform init`.
- Recommended improvements: add terraform formatting step, module structure, per-AZ subnet CIDR calculation, and automated tests for generated output.

Files generated
---------------
- `main.tf`, `variables.tf`, `outputs.tf`, and `README.md` are rendered into the output directory you choose.

Requirements
------------
- Python with Jinja2 installed (see `requirements.txt`).

Backend creation helpers
------------------------
If you want TerraGen to create the S3 bucket and DynamoDB table for Terraform remote state safely, use the included CloudFormation template and IAM policy as a guide:

- `backend-cfn.yaml` — CloudFormation template to create the S3 bucket and the DynamoDB table for state locking.
- `backend_iam_policy.json` — Example IAM policy (use in IAM console or attach to a role) that grants permissions to create and manage the bucket and table. Replace the `${BucketName}`, `${Region}`, `${Account}`, and `${DDBTableName}` placeholders with real values.

Example: deploy the CloudFormation stack using AWS CLI (replace parameters):

```powershell
aws cloudformation deploy --template-file backend-cfn.yaml --stack-name terra-backend --parameter-overrides BucketName=my-project-tfstate DDBTableName=my-project-locks VersioningEnabled=true
```

After creating the bucket and table you can run Terraform in the generated folder with the backend configured.

Filling the IAM policy
----------------------
Use `fill_backend_policy.py` to replace placeholders in `backend_iam_policy.json` and produce a policy JSON ready to use:

```powershell
python fill_backend_policy.py --bucket my-project-tfstate --ddb my-project-locks --account 123456789012 --region us-east-1 --out policy.json
```

To apply the policy directly, use `--apply` and ensure your AWS credentials are configured and have permission to create IAM policies.
