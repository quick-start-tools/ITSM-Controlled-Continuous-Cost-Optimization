import json
import boto3
import ssm_functions
import datetime

def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    
    if event['resource'] == "/manage-insight/approve":
        approve_insight(event)
    elif event['resource'] == "/manage-insight/close":
        close_insight(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def approve_insight(event):
    
    try:
        
        input = json.loads(event['body'])
        print("Approval request received for " + input['serviceType'] + " instance with name " + input['name'] + " and resource id " + input['resourceId'] + ".")
        
        parameterKey = ""
        if input['serviceType'] == "EC2":
            parameterKey = "/densify/iaas/ec2/" + input['resourceId'] + "/instanceType"
        elif input['serviceType'] == "RDS":
            parameterKey = "/densify/iaas/rds/" + input['name'] + "/dbInstanceClass"        
        
        parameter = ssm_functions.getParameter(parameterKey, input['region'])
        tags = ssm_functions.list_tags('Parameter', parameterKey, input['region'])
        label = ssm_functions.getParameterCurrentLabels(parameterKey, input['region'])
        
        if label[0] == 'Initialize':
            version = ssm_functions.putParameter(parameterKey, tags['recommendedType'], tags['name'], input['region'])
            ssm_functions.addTagsToResource('Parameter', parameterKey, [{'Key': 'approvalType', 'Value': 'Approved'}], input['region'])
            ssm_functions.labelParameterVersion(parameterKey, version, ["Approved"], input['region'])
            ssm_functions.putParameter('/densify/config/lastUpdatedTimestamp', datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), 'Last time densify pushed an update', input['region'])
        
    except Exception as error:
        print("Exception caught while approving request. " + str(error))
        return False
        
def close_insight(event):
    
    try:
        
        input = json.loads(event['body'])
        print("Close request received for " + input['serviceType'] + " instance with name " + input['name'] + " and resource id " + input['resourceId'] + ".")
        
        parameterKey = ""
        if input['serviceType'] == "EC2":
            parameterKey = "/densify/iaas/ec2/" + input['resourceId'] + "/instanceType"
        elif input['serviceType'] == "RDS":
            parameterKey = "/densify/iaas/rds/" + input['name'] + "/dbInstanceClass"        
        
        parameter = ssm_functions.getParameter(parameterKey, input['region'])
        tags = ssm_functions.list_tags('Parameter', parameterKey, input['region'])
        label = ssm_functions.getParameterCurrentLabels(parameterKey, input['region'])
        
        if label[0] == 'Approved':
            version = ssm_functions.putParameter(parameterKey, tags['recommendedType'], tags['name'], input['region'])
            ssm_functions.labelParameterVersion(parameterKey, version, ["Closed"], input['region'])

    except Exception as error:
        print("Exception caught while approving request. " + str(error))
        return False