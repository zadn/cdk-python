
# CDK Python Project

This CDK Project achieves:

* A Simple EKS cluster with one nodegroup
* Nginx Ingress controller in the EKS cluster using Helm Chart
* Lambda backed CustomResource

The Nginx Ingress controller replica count is configured by an SSM Parameter value. When the SSM Parameter value is 
`staging` or `production`, then the replicacount is set to 2. If the parameter is `development` or something undefined,
the replicacount will be set to 1. The Helm replica values map is returned by the CustomResource Lambda function.

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


# Running Unit Tests with pytest

Make sure the pytest package is installed, and then run `pytest`

```bash
pip install -r requirements.txt
pytest
```
