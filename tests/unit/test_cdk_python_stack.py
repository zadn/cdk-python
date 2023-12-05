import pytest
import os
import sys
import boto3
import json

resource_directory = os.path.abspath('resources/LambdaCustomResource')
sys.path.append(resource_directory)

from index import on_event

SSM_PARAM_NAME = "/platform/account/env_test"

def obtain_helm_with_environment(env_name, expected_replica_count):
    # First put the "development" value in SSM
    ssm = boto3.client('ssm')
    ssm.put_parameter(
        Name=SSM_PARAM_NAME,
        Type='String',
        Value=env_name,
        Overwrite=True
    )

    event_data = {
        "RequestType": "Update",
        "PhysicalResourceId": "InputResourceId",
        "ResourceProperties": {
            "ssm_parameter_name": SSM_PARAM_NAME
        }
    }

    helm_value = json.dumps({
        "controller": {
            "replicaCount": expected_replica_count
        }
    })
    expected_response = {
        "PhysicalResourceId": "InputResourceId",
        "Data": {
            "helm_values": helm_value
        }
    }
    return event_data, expected_response

def test_lambda_development():
    environment_name = 'development'
    expected_replica_count = 1
    event_data, expected_response = obtain_helm_with_environment(environment_name, expected_replica_count)

    assert on_event(event_data, 'context') == expected_response

def test_lambda_staging():
    environment_name = 'staging'
    expected_replica_count = 2
    event_data, expected_response = obtain_helm_with_environment(environment_name, expected_replica_count)

    assert on_event(event_data, 'context') == expected_response

def test_lambda_production():
    environment_name = 'production'
    expected_replica_count = 2
    event_data, expected_response = obtain_helm_with_environment(environment_name, expected_replica_count)

    assert on_event(event_data, 'context') == expected_response
