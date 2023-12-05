import json

from helm import helm_handler

def lambda_handler(event, context):
  print(json.dumps(dict(event, ResponseURL='...')))

  resource_type = event['ResourceType']
#   if resource_type == 'Custom::AWSCDK-EKS-KubernetesResource':
#     return apply_handler(event, context)

  if resource_type == 'Custom::AWSCDK-EKS-HelmChart':
    return helm_handler(event, context)

#   if resource_type == 'Custom::AWSCDK-EKS-KubernetesPatch':
#     return patch_handler(event, context)

#   if resource_type == 'Custom::AWSCDK-EKS-KubernetesObjectValue':
#     return get_handler(event, context)

  raise Exception("unknown resource type %s" % resource_type)