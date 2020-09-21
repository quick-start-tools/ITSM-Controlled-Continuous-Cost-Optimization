import json
import boto3
import ssm_functions
import datetime

def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    
    if event['resource'] == "/approve":
        approve_insight(event)
    elif event['resource'] == "/close":
        close_insight(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Sucessfully Executed!')
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
        
        parameter = ssm_functions.getParameter(parameterKey, region=input['region'])
        tags = ssm_functions.list_tags('Parameter', parameterKey, region=input['region'])
        label = ssm_functions.getParameterCurrentLabels(parameterKey, region=input['region'])
        
        if label[0] == 'Initialize':
            version = ssm_functions.putParameter(parameterKey, tags['recommendedType'], description=tags['name'], region=input['region'])
            ssm_functions.addTagsToResource('Parameter', parameterKey, [{'Key': 'approvalType', 'Value': 'Approved'}], region=input['region'])
            ssm_functions.labelParameterVersion(parameterKey, version, ["Approved"], region=input['region'])
            ssm_functions.putParameter('/densify/config/lastUpdatedTimestamp', datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), description='Last time densify pushed an update', region=input['region'])
        
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
        
        parameter = ssm_functions.getParameter(parameterKey, region=input['region'])
        tags = ssm_functions.list_tags('Parameter', parameterKey, region=input['region'])
        label = ssm_functions.getParameterCurrentLabels(parameterKey, region=input['region'])
        
        if label[0] == 'Executed':
            version = ssm_functions.putParameter(parameterKey, tags['recommendedType'], description=tags['name'], region=input['region'])
            ssm_functions.labelParameterVersion(parameterKey, version, ["Closed"], region=input['region'])

    except Exception as error:
        print("Exception caught while approving request. " + str(error))
        return False