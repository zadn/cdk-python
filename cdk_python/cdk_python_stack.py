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
    aws_ssm as ssm,
    custom_resources as cr,
    aws_lambda as _lambda,
    CfnOutput,
    CustomResource
)
from constructs import Construct

# Set the Variables here
EKS_CLUSTER_NAME = "ckd-eks-cluster"
SSH_KEYPAIR_NAME = "eks-ssh-keypair"
EKS_NODEGROUP_NAME = "cdk-eks-nodegroup"
EKS_NODEGROUP_INSTANCE_TYPE = "t4g.small"
SSM_PARAMETER_NAME = "/platform/account/env"
SSM_PARAMETER_VALUE = "staging"
ADD_TO_AWS_AUTH = {
    "iam_user_names": [
    ],
    "iam_role_names": [
    ]
}
CUSTOM_LAMBDA_FN_NAME = "CustomResourceLambda"

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

        # --------------------------------------------------------------------------------------------------------------

        ssm_parameter = ssm.StringParameter(
            self, f"{SSM_PARAMETER_NAME}-{construct_id}",
            parameter_name=SSM_PARAMETER_NAME,
            description="Parameter which stores the environment to be used",
            string_value=SSM_PARAMETER_VALUE
        )

        lambda_role = iam.Role(
            scope=self,
            id=f"{CUSTOM_LAMBDA_FN_NAME}-role",
            role_name=f"{CUSTOM_LAMBDA_FN_NAME}-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "SSMParameterAccessPolicy":
                    iam.PolicyDocument(statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ssm:GetParameter"
                            ],
                            resources=[
                                ssm_parameter.parameter_arn
                            ],
                            effect=iam.Effect.ALLOW,
                        )
                    ])
            },
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        # Lambda Function
        cust_res_lambda = _lambda.Function(
                self, f'{CUSTOM_LAMBDA_FN_NAME}-{construct_id}',
                runtime=_lambda.Runtime.PYTHON_3_10,
                code=_lambda.Code.from_asset('resources/LambdaCustomResource'),
                handler="index.on_event",
                function_name=CUSTOM_LAMBDA_FN_NAME,
                role=lambda_role,
                timeout=Duration.minutes(5)
            )

        # CustomResource
        res_provider = cr.Provider(
            self, f'crProvider-{construct_id}',
            on_event_handler=cust_res_lambda
        )
        c_resource = CustomResource(
            self, f'cust_res-{construct_id}',
            service_token=res_provider.service_token,
            properties={
                "ssm_parameter_name": str(ssm_parameter.parameter_name)
            }
        )
        cr_helm_values = c_resource.get_att('helm_values').to_string()
        # CfnOutput(
        #     self, id=f'HelmValues-{construct_id}',
        #     value=cr_helm_values
        # )

        # --------------------------------------------------------------------------------------------------------------

        # Install Helm chart
        helm_values = json.loads(cr_helm_values)
        nginx_helm_chart = eks.HelmChart(self, "NginxIngress",
                                         cluster=cluster,
                                         chart="nginx-ingress",
                                         release="nginx-ingress-controller",
                                         repository="https://helm.nginx.com/stable",
                                         namespace="default",
                                         values=helm_values
                                         )

        nginx_helm_chart.node.add_dependency(c_resource)
