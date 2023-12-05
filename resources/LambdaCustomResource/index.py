import boto3
import json

client = boto3.client('ssm')
def on_event(event, context):
    print(event)
    request_type = event['RequestType'].lower()
    if request_type == 'create':
        return on_create(event)
    if request_type == 'update':
        return on_update(event)
    if request_type == 'delete':
        return on_delete(event)
    raise Exception(f'Invalid request type: {request_type}')


def on_create(event):
    props = event["ResourceProperties"]
    print(f'create new resource with {props=}')

    ssm_parameter_name = props['ssm_parameter_name']
    helm_nginx_values = prepare_helm_values(ssm_parameter_name)
    physical_id = ssm_parameter_name
    return {
        'PhysicalResourceId': physical_id,
        'Data': {
            'helm_values': helm_nginx_values
        }
    }

def on_update(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]
    print(f'update resource {physical_id} with {props=}')

    ssm_parameter_name = props['ssm_parameter_name']
    helm_nginx_values = prepare_helm_values(ssm_parameter_name)

    print(f"SSM Parameter {ssm_parameter_name}  | Helm Values : {str(helm_nginx_values)}")
    return {
        'PhysicalResourceId': physical_id,
        'Data': {
            'helm_values': helm_nginx_values
        }
    }


def on_delete(event):
    physical_id = event["PhysicalResourceId"]
    props = event["ResourceProperties"]
    print(f'no actions for deletion')

    return {'PhysicalResourceId': physical_id}


def prepare_helm_values(ssm_parameter_name):

    parameter = client.get_parameter(Name=ssm_parameter_name)
    parameter_value = parameter['Parameter']['Value']

    if parameter_value == "staging" or parameter_value == "production":
        replica_count = 2
    else:
        replica_count = 1

    helm_nginx_values = {
        "controller": {
            "replicaCount": replica_count
        }
    }

    return json.dumps(helm_nginx_values)
