
# CDK Python Project

This CDK Project achieves:

* A Simple EKS cluster with one nodegroup
* Nginx Ingress controller in the EKS cluster using Helm Chart
* Lambda backed CustomResource

The Nginx Ingress controller replica count is configured by an SSM Parameter value. When the SSM Parameter value is 
`staging` or `production`, then the replicacount is set to 2. If the parameter is `development` or something undefined,
the replicacount will be set to 1. The Helm replica count is updated using the Lambda CustomResource.

As of now, the SSM Parameter creation is not part of this CDK Project, and it assumes the SSM Parameter already exists. 
This has not been added to this project yet because the SSM parameter creation, when it's a fresh install, happens at 
deploy time, and the SSM parameter fetch with Boto3 happens even before the synth happens, so once we can define 
the ssm parameter creation within Cloudformation as a dependency of boto3 ssm fetch, we can add it to this CDK Project. 


# Setting up CDK

```bash
# Setup virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install the requirements
pip install -r requirements.txt

# To synthesize CF template
cdk synth

# To deploy the cdk project
cdk deploy
```