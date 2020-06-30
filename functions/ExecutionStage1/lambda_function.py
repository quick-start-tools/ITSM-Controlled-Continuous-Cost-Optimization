import json
import boto3
import time
import datetime

def lambda_handler(event, context):
    # TODO implement

    resp = False
    if isStackInSync(event['stackId']) == True:
        print("Stack is not drifted.  Proceeding with update.")
        resp = cf_update_stack(event['stackId'], context)
    else:
        createErrorOpsItem(event['stackId'], "Stack drifted, cannot perform update.")

    if resp == True:
        return {'statusCode': 200, 'body': json.dumps('Successfully executed.')}
    else:
        return {'statusCode': -1, 'body': json.dumps('Did not execute successfully.')}

def lambda_execute(functionName, eventObj):
    
    try:
        
        jsonStr = json.dumps(eventObj)

        client = boto3.client('lambda')
        response = client.invoke(
			FunctionName=functionName,
			InvocationType='RequestResponse',
			Payload=jsonStr.encode('utf-8')
		)
        
        payload = json.loads(response['Payload'].read())
        statusCode = payload['statusCode']
        body = payload['body']
        
        print("Lambda executed with return code: " + str(statusCode) + " and payload: " + str(body))
        if response['StatusCode'] != 200:
        	raise Exception(str(body))
        
        return body
        
    except Exception as error:
        print("Error encountered while executing lambda[" + functionName + "].")
        print(error)
        return False
        
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
        print("Exception encountered while getting opsItems.\n" + str(error))
        return False
        
def update_opsItems(stackId, stackStatus):
	
	try:
		
		print("Updating all OpsItems with status of execution.")
		
		client = boto3.client('ssm')

		OpsItemFilters=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-id\",\"value\":\"" + stackId + "\"}",
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

		for opsItem in relatedOpsItems:
			response = client.update_ops_item(
			    OperationalData={
			        'executionStatus': {
			            'Value': stackStatus,
			            'Type': 'String'
			        }
			    },
			    OpsItemId=opsItem['OpsItemId']
			)

		return True

	except Exception as error:
	    print("Exception encountered while updating opsItems.\n" + str(error))
	    return False

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
		
		return True
				
	except Exception as error:
		print("Exception encountered while creating an error opsItem.\n" + str(error))
		return False

def cf_update_stack(stackId, context):

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
	    print("Exception encountered while performing a stack update.")
	    print(error)
	    createErrorOpsItem(stackId, "StackUpdate Error")
	    update_opsItems(stackId, "FAILED - " + str(datetime.datetime.utcnow()))
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
		return False