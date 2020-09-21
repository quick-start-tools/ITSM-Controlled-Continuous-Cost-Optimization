# -*- coding: utf-8 -*-
"""
Created on Mon Aug 17 10:42:50 2020

@author: draveendran
"""

import json
import boto3
import datetime
import os

def lambda_handler(event, context):
    # TODO implement
    
    try:
        
        print("Incoming event: " + str(event))

        if int(event['duration']) < 1 or int(event['duration']) > 24:
            raise Exception ("Duration can only be between 1-24 hours.  Specify as an integer.")
        
        opsItemId = event['opsItemId']
        opsItem = getOpsItem(opsItemId)
        maintenanceWindow = findActiveMaintenanceWindow("mw-" + opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value'])
        
        windowId = None
        if maintenanceWindow != False:
            print("Updating existing maintenance window.")
            windowId = maintenanceWindow['WindowId']
            updateMaintenanceWindow(windowId, event)
        else:
            print("Creating a new maintenance window.")
            windowId = createMaintenanceWindow(event)
            if windowId == False:
                raise Exception ("Window creation failed.")
                
            print("Registering tasks.")
            register_task(windowId, opsItemId)
        
        print("Updating tags on maintenance window.")
        updateMaintenanceWindowTags(windowId, opsItemId)
        
        print("Updating all associated opsItems.")
        updateOpsItems(windowId, opsItemId, event)
        
        print("Update assoicated parameters")
        updateParameters(opsItemId)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Maintenance window scheduled.')
        }
    
    except Exception as error:
        print("Exception encountered: " + str(error))
        return {'statusCode': -1, 'body': json.dumps({'message': str(error)})}

def updateParameters(opsItemId):
    
    try:
        
        relatedOpsItems = getRelatedOpsItems(opsItemId)
        
        for opsItem in relatedOpsItems:
            parameterKey = getOpsItem(opsItem['OpsItemId'])['OpsItem']['OperationalData']['parameterKey']['Value']
            version = putParameter(parameterKey, getParameter(parameterKey)['Parameter']['Value'])
            labelParameterVersion(parameterKey, version, ['Scheduled'])
            
    except Exception as error:
        print(error)
        return False

def register_task(windowId, opsItemId):
    
    try:
        
        client = boto3.client('ssm')
        
        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )   
        
        payload = {}
        payload['stackId'] = opsItem['OpsItem']['OperationalData']['cloudformation:stack-id']['Value']
        payload['windowId'] = windowId
        payload['stage'] = "1"
        jsonStr = json.dumps(payload)

        accountId = payload['stackId'].split(":")[4]
        region = payload['stackId'].split(":")[3]
        
        ssm_doc = client.get_document(
            Name='ScheduleMaintenanceWindow'
        )
        
        response = client.register_task_with_maintenance_window(
            WindowId=windowId,
            Targets=[
                {
                    'Key': 'InstanceIds',
                    'Values': [
                        'i-00000000000000000',
                    ]
                },
            ],
            TaskArn='arn:aws:lambda:' + region + ':' + accountId + ':function:ManageUpdateProcess',
            ServiceRoleArn=json.loads(ssm_doc['Content'])['assumeRole'],
            TaskType='LAMBDA',
            TaskInvocationParameters={
                'Lambda': {
                    'Payload': jsonStr.encode('utf-8')
                }
            },
            MaxConcurrency='1',
            MaxErrors='1',
            Name='Update-Stack'
            
        )
        
        print(response)
        
    except Exception as error:
        print(error)

def updateOpsItems(windowId, opsItemId, event):
    
    try:
        
        client = boto3.client('ssm')

        relatedOpsItems = getRelatedOpsItems(opsItemId)

        opsData = {}
        opsData['scheduledMaintenanceWindowDetails'] = {}
        opsData['scheduledMaintenanceWindowDetails']['Value'] = 'WindowId=' + windowId
        opsData['scheduledMaintenanceWindowDetails']['Value'] += '\nCronExpression=' + event['cronExpression']
        opsData['scheduledMaintenanceWindowDetails']['Value'] += '\nDuration=' + event['duration']
        opsData['scheduledMaintenanceWindowDetails']['Type'] = 'String'
        
        response = {}
        for opsItem in relatedOpsItems:
            response = client.update_ops_item(
                Status='InProgress',
                OperationalData=opsData,
                OpsItemId=opsItem['OpsItemId']
            )
        
        print(response)

    except Exception as error:
        print(error)

def getRelatedOpsItems(opsItemId):
    
    try:
        
        client = boto3.client('ssm')
        
        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )
        
        stackId = opsItem['OpsItem']['OperationalData']['cloudformation:stack-id']['Value']
        stackName = opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value']
        
        OpsItemFilters=[
            {
                'Key': 'OperationalData',
                'Values': [
                    "{\"key\":\"cloudformation:stack-name\",\"value\":\"" + stackName + "\"}",
                ],
                'Operator': 'Equal'
            },
            {
                'Key': 'Status',
                'Values': [
                    "Open",
                    "InProgress"
                ],
                'Operator': 'Equal'
            }
        ]
        
        relatedOpsItems = getOpsItems(OpsItemFilters)
        
        return relatedOpsItems
        
    except Exception as error:
        print(error)

def getOpsItems(filter):
    
    try:
        
        client = boto3.client('ssm')
        
        response = client.describe_ops_items(
            OpsItemFilters=filter
        )
        
        opItemIds = []
        for opsItem in response['OpsItemSummaries']:
            opItemIds.append({'OpsItemId': opsItem['OpsItemId']})
        
        return opItemIds
        
    except Exception as error:
        print(error)
        
def updateMaintenanceWindowTags(windowId, opsItemId):
    
    try:
        
        client = boto3.client('ssm')

        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )
        
        stackId = opsItem['OpsItem']['OperationalData']['cloudformation:stack-id']['Value']
        stackName = opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value']

        response = client.add_tags_to_resource(
            ResourceType='MaintenanceWindow',
            ResourceId=windowId,
            Tags=[
                {
                    'Key': 'cloudformation:stack-name',
                    'Value': stackName                  
                },
                {
                    'Key': 'LastModifiedDate',
                    'Value': str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
                }
            ]
        )
        
        print(response)

    except Exception as error:
        print(error)

def updateMaintenanceWindow(windowId, event):
    
    try:
    
        client = boto3.client("ssm")

        opsItem = client.get_ops_item(
            OpsItemId=event['opsItemId']
        )
        
        windowName = "mw-" + opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value']
        
        response = client.update_maintenance_window(
            WindowId=windowId,
            Name=windowName,
            Schedule="at(" + event['cronExpression'] + ")",
            ScheduleTimezone=event['timezone'],
            Duration=int(event['duration']),
            Cutoff=1,
            AllowUnassociatedTargets=True,
            Enabled=True,
            Replace=True
        )
        
        print(response)
    
    except Exception as error:
        print(error)
   
def createMaintenanceWindow(event):
        
    try:
    
        client = boto3.client("ssm")

        opsItem = client.get_ops_item(
            OpsItemId=event['opsItemId']
        )
        
        windowName = "mw-" + opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value']
        
        response = client.create_maintenance_window(
            Name=windowName,
            Schedule="at(" + event['cronExpression'] + ")",
            ScheduleTimezone=event['timezone'],
            Duration=int(event['duration']),
            Cutoff=1,
            AllowUnassociatedTargets=True
        )
        
        print(response)
        
        return response['WindowId']
    
    except Exception as error:
        print("Exception encountered while trying to create a maintenance window.")
        print(error)
        return False
    
#SSM Functions
def getOpsItem(OpsItemId, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        response = ssm_client.get_ops_item(
            OpsItemId=OpsItemId
        )

        return response

    except Exception as error:
        print("Exception encountered while getting opsItem [" + OpsItemId + "]: " + str(error))
        return False

def findActiveMaintenanceWindow(name, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
        
    try:
        
        response = ssm_client.describe_maintenance_windows(
            Filters=[
                {
                    'Key': 'Name',
                    'Values': [
                        name
                    ]
                },
                {
                    'Key': 'Enabled',
                    'Values': [
                        'True'
                    ]
                }
            ]
        )
        
        print(response)
                
        if len(response['WindowIdentities']) != 1:
            raise Exception ("Total number of maintenance window(s) " + str(response['WindowIdentities']) + " found is " + str(len(response['WindowIdentities'])) + ".  There should only exist 1.")
        
        return response['WindowIdentities'][0]
        
    except Exception as error:
        print("Exception caught while locating maintenance window [" + name + "]: " + str(error))
        return False

def putParameter(parameterKey, value, **kwargs):
   
    region = os.environ['AWS_REGION']
    desc = ""

    if 'region' in kwargs:
        region = kwargs['region']

    if 'description' in kwargs:
        desc = kwargs['description']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        response = ssm_client.put_parameter(
            Name=parameterKey,
            Description=desc,
            Value=value,
            Type='String',
            Overwrite=True,
            Tier='Standard'
        )

        return response['Version']

    except Exception as error:
        print("Exception caught while creating/updating parameter[" + parameterKey + "] in region[" + region + "]: " + str(error))
        return False

def getParameter(key, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        response = ssm_client.get_parameter(
            Name=key,
            WithDecryption=True
        )

        return response

    except Exception as error:
        print("Exception caught during parameter retreival for parameter[" + key + "] in region[" + region + "]: " + str(error))
        return False

def labelParameterVersion(parameterKey, version, labels, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        ssm_client.label_parameter_version(
            Name=parameterKey,
            ParameterVersion=version,
            Labels=labels
        )

        return True

    except Exception as error:
        print("Exception caught while labeling parameter[" + parameterKey + "] in region[" + region + "]: " + str(error))
        return False