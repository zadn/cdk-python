from aws_cdk.lambda_layer_kubectl_v28 import KubectlV28Layer
from aws_cdk.lambda_layer_awscli import AwsCliLayer
import boto3
import json
from aws_cdk import (
    Duration,
    Stack,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    custom_resources as cr,
    aws_lambda as _lambda,
    CfnOutput
)
from constructs import Construct

# Set the Variables here
EKS_CLUSTER_NAME = "ckd-eks-cluster"
SSH_KEYPAIR_NAME = "eks-ssh-keypair"
EKS_NODEGROUP_NAME = "cdk-eks-nodegroup"
EKS_NODEGROUP_INSTANCE_TYPE = "t4g.small"
SSM_PARAMETER_NAME = "/platform/account/env"
ADD_TO_AWS_AUTH = {
    "iam_user_names": [
    ],
    "iam_role_names": [
    ]
}
CUSTOM_LAMBDA_FN_NAME = "custom-helm-lambda"

class CdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Provisioning a cluster
        cluster = eks.Cluster(self, EKS_CLUSTER_NAME,
                              cluster_name=EKS_CLUSTER_NAME,
                              version=eks.KubernetesVersion.V1_28,
                              kubectl_layer=KubectlV28Layer(self, "kubectl"),
                              default_capacity=0
                              )

        # Add an EC2 KeyPair for SSH access
        ssh_key_pair = ec2.CfnKeyPair(self, SSH_KEYPAIR_NAME,
                                      key_name=SSH_KEYPAIR_NAME
                                      )
        # Add a managed Node Group
        node_group = cluster.add_nodegroup_capacity(EKS_NODEGROUP_NAME,
                                                    instance_types=[ec2.InstanceType(EKS_NODEGROUP_INSTANCE_TYPE)],
                                                    disk_size=20,
                                                    min_size=1,
                                                    max_size=2,
                                                    desired_size=1,
                                                    remote_access=eks.NodegroupRemoteAccess(
                                                        ssh_key_name=ssh_key_pair.key_name),
                                                    tags={
                                                        'Name': EKS_NODEGROUP_NAME
                                                    }
                                                    )

        # Add IAM Users and roles into aws-auth for cluster access
        for iam_user_name in ADD_TO_AWS_AUTH['iam_user_names']:
            cluster.aws_auth.add_user_mapping(
                user=iam.User.from_user_name(self, iam_user_name, iam_user_name),
                username=iam_user_name,
                groups=["system:masters"]
            )
        for iam_role_name in ADD_TO_AWS_AUTH['iam_role_names']:
            cluster.aws_auth.add_masters_role(
                role=iam.Role.from_role_name(self, iam_role_name, iam_role_name),
                username=iam_role_name
            )

        # Lambda CustomResource Role
        lambda_role = iam.Role(self, "Role",
                               assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                               role_name=f"{CUSTOM_LAMBDA_FN_NAME}-role",
                               description="Custom Helm Lambda Resource",
                               inline_policies={
                                   "eks_cluster_access": iam.PolicyDocument(
                                       statements=[iam.PolicyStatement(
                                           actions=["eks:DescribeCluster"],
                                           resources=[cluster.cluster_arn]
                                       )]
                                   )
                               }
                               )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                managed_policy_name="service-role/AWSLambdaBasicExecutionRole"))

        # Allow the CustomResource Lambda role to access the cluster
        cluster.aws_auth.add_masters_role(role=lambda_role, username=lambda_role.role_name)

        # Create the Lambda function for the CustomResource
        cust_res_lambda = _lambda.Function(
            self, f'{CUSTOM_LAMBDA_FN_NAME}-{construct_id}',
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset('resources/CustomHelmLambda'),
            handler="lambda_function.lambda_handler",
            function_name=CUSTOM_LAMBDA_FN_NAME,
            role=lambda_role,
            timeout=Duration.minutes(15)
        )
        cust_res_lambda.add_layers(KubectlV28Layer(self, "KubectlV28Layer"))
        cust_res_lambda.add_layers(AwsCliLayer(self, "AwsCliLayer"))

        # Fetch SSM Parameter with Boto3
        client = boto3.client('ssm')
        parameter = client.get_parameter(Name=SSM_PARAMETER_NAME)
        parameter_value = parameter['Parameter']['Value']
        CfnOutput(self, id=f"ParamValue-{construct_id}",
                  value=str(parameter_value),
                  export_name="ParamValue"
                  )

        if parameter_value == "staging" or parameter_value == "production":
            replica_count = 2
        else:
            replica_count = 1

        CfnOutput(self, id=f"ReplicaCount",
                  value=str(replica_count),
                  export_name="ReplicaCount"
                  )

        # Install Helm chart
        nginx_helm_chart = eks.HelmChart(self, "NginxIngress",
                                         cluster=cluster,
                                         chart="nginx-ingress",
                                         release="nginx-ingress-controller",
                                         repository="https://helm.nginx.com/stable",
                                         namespace="default"
                                         )

        lambda_payload = {
            "RequestType": "Update",
            "ResourceType": "Custom::AWSCDK-EKS-HelmChart",
            "ResourceProperties": {
                "Repository": nginx_helm_chart.repository,
                "Values": "{\"controller\":{\"replicaCount\":%s}}" % replica_count,
                "ClusterName": cluster.cluster_name,
                "Release": "nginx-ingress-controller",
                "Chart": nginx_helm_chart.chart
            }
        }

        # Define the AWSCustomResource
        c_resource = cr.AwsCustomResource(
            self,
            f"CustomResource-{construct_id}",
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                physical_resource_id=cr.PhysicalResourceId.of("Trigger"),
                parameters={
                    "FunctionName": cust_res_lambda.function_name,
                    "InvocationType": "RequestResponse",
                    "Payload": json.dumps(lambda_payload)
                }
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[cust_res_lambda.function_arn]
                )
            ])
        )
        c_resource.node.add_dependency(nginx_helm_chart)
