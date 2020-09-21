# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 10:37:24 2020

@author: draveendran
"""


import json
import boto3
import time
import datetime
import ssm_functions

def lambda_handler(event, context):
    # TODO implement
    
    print("Executor triggered with event [" + str(event) + "].")
    
    if 'stage' in event and event['stage'] == '1':
        print("Request to execute cloudformation stack-update on " + str(event['stackId']) + " received.")
        if isStackInSync(event['stackId']) == True:
            print("Stack is not drifted.  Proceeding with update.")
            if updateStack(event['stackId'], context) == True:
                print("Cloudformation stack update has been triggered successfully.")
            else:
                print("Cloudformation stack update failed to trigger.  Please investigate and re-schedule for execution.")
        else:
            print("Stack is currently drifted, so not attempting stack update.  Please investigate and re-schedule for execution.")
    else:
        print("Request to process a stack event received.")
        message = {}
        for line in event['Records'][0]['Sns']['Message'].split("\n"):
            if len(line.split("=")) == 2:
                message[line.split("=")[0]] = line.split("=")[1][1:-1]
        print(str(message))
        
        if message['LogicalResourceId'] == message['StackId'].split("/")[1]:
            print("Main stack event detected.")
            completion_states = ['UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE','UPDATE_ROLLBACK_FAILED']
            if message['ResourceStatus'] in completion_states:
                if process_main_stackEvent(message) == True:
                    print("Stack event processed successfully.")
                else:
                    print("Failed to process stack event.")
            else:
                print("Ignoring this request as main stack event state is not in " + str(completion_states))
        else:
            print("Resource [" + str(message['LogicalResourceId']) + "] stack event detected.")
            if process_resource_stackEvent(message) == True:
                print("Stack event processed successfully.")
            else:
                print("Failed to process stack event.")
    
    return {'statusCode': 200, 'body': json.dumps('Processed event.')}
            
def createErrorOpsItem(stackId, message):
    
    try:
        
        print("Creating OpsItem to track error: " + message)
        
        client = boto3.client('ssm')
        
        opsData = {}
        opsData['/aws/resources'] = {}
        opsData['/aws/resources']['Value'] = "[{\"arn\": \"" + stackId + "\"}]"
        opsData['/aws/resources']['Type'] = 'SearchableString'

        response = client.create_ops_item(
            Description=message,
            OperationalData=opsData,
            Source='Densify',
            Title=message,
            Category='Recovery',
            Severity='1'
        )

        print(response)
        
        filter=[
            {
                'Key': 'OperationalData',
                'Values': [
                    "{\"key\":\"cloudformation:stack-name\",\"value\":\"" + stackId.split("/")[1] + "\"}",
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
        opsItemIds = ssm_functions.listAllOpsItemIds(filter)
        notes = {"work_notes": "Failed to execute update - " + str(datetime.datetime.utcnow())}
        data = {'executionStatus': {'Value': json.dumps(notes), 'Type': 'String'}}
        ssm_functions.updateOpsItems(opsItemIds, 'InProgress', opsData=data)
        
        return True
                
    except Exception as error:
        print("Exception encountered while creating an error opsItem.\n" + str(error))
        return False

def updateStack(stackId, context):

    try:

        client = boto3.client('cloudformation')

        response = client.update_stack(
            StackName=stackId,
            UsePreviousTemplate=True,
            Capabilities=[
                'CAPABILITY_IAM',
                'CAPABILITY_NAMED_IAM',
                'CAPABILITY_AUTO_EXPAND'
            ]
        )

        print(response)
        
        return True

    except Exception as error:
        print("Exception encountered while performing a stack update. " + str(error))
        createErrorOpsItem(stackId, "Unable to perform a stack update.")
        return False
        
def isStackInSync(stackId):

    try:

        client = boto3.client('cloudformation')
        
        response = client.describe_stacks(
            StackName=stackId,
        )

        #Perform drift detection
        driftLastChecked = 0
        if 'LastCheckTimestamp' in response['Stacks'][0]['DriftInformation']:
            driftLastChecked = response['Stacks'][0]['DriftInformation']['LastCheckTimestamp']
        
        waitTimeForDriftDetection = 300
        driftDetectionCheckInterval = 10

        response = client.detect_stack_drift(
            StackName=stackId,
        )
        StackDriftDetectionId = response['StackDriftDetectionId']

        while waitTimeForDriftDetection > 0:
            time.sleep(driftDetectionCheckInterval)
            waitTimeForDriftDetection-=driftDetectionCheckInterval
            response = client.describe_stack_drift_detection_status(
                StackDriftDetectionId=StackDriftDetectionId
            )
            if response['Timestamp'] != driftLastChecked:
                if response['DetectionStatus'] == 'DETECTION_FAILED':
                    print("Drift detection did not complete successfully.")
                    return False
                elif response['DetectionStatus'] == 'DETECTION_COMPLETE':
                    if response['StackDriftStatus'] != 'IN_SYNC':
                        print("Drift detection complete, however the stack is not 'In Sync'.")
                        return False
                    else:
                        return True
        
        return False
    except Exception as error:
        print("Exception encountered during drift detection.  " + str(error))
        createErrorOpsItem(stackId, "Stack is drifted.")
        return False

def process_main_stackEvent(message):
    
    try:

        #Validate that stack is in a valid state
        
        client = boto3.client('cloudformation')
        
        response = client.describe_stacks(
            StackName=message['StackId']
        )
        
        if response['Stacks'][0]['StackStatus'] != message['ResourceStatus']:
            raise Exception ("Stack is in an invalid state. " + response['Stacks'][0]['StackStatus'])
        
        filter=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-name\",\"value\":\"" + message['StackName'] + "\"}",
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
        
        opsItemIds = ssm_functions.listAllOpsItemIds(filter)        
        windowId = ssm_functions.findActiveMaintenanceWindow("mw-" + message['StackName'])

        response = ssm_functions.describeMaintenanceWindowExecutions(windowId)
        work_start = response['WindowExecutions'][0]['StartTime']
        work_end = datetime.datetime.now()

        notes = {"work_notes": message['ResourceStatus'], "work_start": str(work_start), "work_end": str(work_end)}
        ssm_functions.updateOpsItems(opsItemIds, 'InProgress', opsData={'executionStatus': {'Value': json.dumps(notes), 'Type': 'String'}})

        if message['ResourceStatus'] == 'UPDATE_COMPLETE':

            for opsItemId in opsItemIds:
                opsItem = ssm_functions.getOpsItem(opsItemId)
                parameterKey = opsItem['OpsItem']['OperationalData']['parameterKey']['Value']
                parameter = ssm_functions.getParameter(parameterKey)
                version = ssm_functions.putParameter(parameterKey, parameter['Parameter']['Value'])
                ssm_functions.labelParameterVersion(parameterKey, version, ['Executed'])
            
        else:
            
            createErrorOpsItem(message['StackId'], "Stack did not update correctly.")
        
        return True
        
    except Exception as error:
        print("Exception caught while handling main stack event.\n" + str(error))
        return False
    
def process_resource_stackEvent(message):
    
    try:
        
        filter=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-name\",\"value\": \"" + message['StackName'] + "\"}"
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
        
        opsItemSummaries = ssm_functions.describeOpsItems(filter)
        
        opsItem = False
        for opsItemTmp in opsItemSummaries['OpsItemSummaries']:
            if opsItemTmp['OperationalData']['cloudformation:logical-id']['Value'] == message['LogicalResourceId']:
                opsItem = ssm_functions.getOpsItem(opsItemTmp['OpsItemId'])
                break
        
        if opsItem == False:
            raise Exception ("A single opsItem was not located.")
		
        opsItemId = opsItem['OpsItem']['OpsItemId']
        eventId = message['ResourceStatus'] + "-" + message['Timestamp']
        
        if 'stackEvents' in opsItem['OpsItem']['OperationalData']:
            eventId = eventId + "\n" + opsItem['OpsItem']['OperationalData']['stackEvents']['Value']
        
        ssm_functions.updateOpsItems([opsItemId], 'InProgress', opsData={'stackEvents': {'Value': eventId, 'Type': 'String'}})
    
        return True
        
    except Exception as error:
        print("Exception encountered while updating opsItem. " + str(error))
        return False