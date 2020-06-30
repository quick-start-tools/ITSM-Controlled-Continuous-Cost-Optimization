import json
import boto3
import datetime

def lambda_handler(event, context):
    # TODO implement

    print("Request received.\n" + str(event))

    message = {}
    for line in event['Records'][0]['Sns']['Message'].split("\n"):
        if len(line.split("=")) == 2:
            message[line.split("=")[0]] = line.split("=")[1][1:-1]
    
    print("Message parsing complete.\n" + str(message))

    resp = False
    if message['LogicalResourceId'] == message['StackId'].split("/")[1]:
        completion_states = ['UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE','UPDATE_ROLLBACK_FAILED']
        if message['ResourceStatus'] in completion_states:
            resp = process_main_stackEvent(message)
        else:
            print("Ignoring this request as main stack event state is not in " + str(completion_states))
            resp = True
    else:
        resp = process_resource_stackEvent(message)
    
    if resp == True:
        print("Updated Successfully.")
        return {'statusCode': 200, 'body': json.dumps('Successfully executed.')}
    else:
        print("Failed to update.")
        return {'statusCode': -1, 'body': json.dumps('Failed to execute.')}

def close_window(windowId):
	
	try:
		
		client = boto3.client('ssm')
		
		response = client.delete_maintenance_window(
		    WindowId=windowId
		)
		
		print(response)
				
	except Exception as error:
		print(error)

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

def getParameter(key):
    
    try:
        
        client = boto3.client('ssm')
        
        parameter = {}
        
        response = client.get_parameter(
            Name=key,
            WithDecryption=True
        )
        
        parameter['Parameter'] = response['Parameter']
        
        response = client.list_tags_for_resource(
            ResourceType='Parameter',
            ResourceId=key
        )
        
        tags = {}
        for tag in response['TagList']:
            tags[tag['Key']] = tag['Value']
        
        parameter['Tags'] = tags

        return parameter
        
    except Exception as error:
        print(error)
        
def process_main_stackEvent(message):
    
    try:

        #Validate that stack is in a valid state
        
        client = boto3.client('cloudformation')
        
        response = client.describe_stacks(
            StackName=message['StackId']
        )
        
        completion_states = ['UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE','UPDATE_ROLLBACK_FAILED']
        if response['Stacks'][0]['StackStatus'] != message['ResourceStatus']:
            raise Exception ("Stack is in an invalid state. " + response['Stacks'][0]['StackStatus'])
        
        OpsItemFilters=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-id\",\"value\":\"" + message['StackId'] + "\"}",
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
		
        opsItemIds = describeOpsItems(OpsItemFilters)
		
        client = boto3.client('ssm')
		
		#Close MW
        opsItem = getOpsItem(opsItemIds[0]['OpsItemId'])
        windowDetails = opsItem['OpsItem']['OperationalData']['scheduledMaintenanceWindowDetails']['Value']
        windowId = windowDetails.split("\n")[0].split("=")[1]

        if message['ResourceStatus'] == 'UPDATE_COMPLETE':
            
            #1. close itsm tickets  3. close ops items
            
            response = client.describe_maintenance_window_executions(
                WindowId=windowId
            )
            work_start = response['WindowExecutions'][0]['StartTime']
            work_end = datetime.datetime.now()

            updateOpsItems(opsItemIds, 'Resolved', message['ResourceStatus'])
            updateITSMTickets(opsItemIds, 'close', {"work_notes": message['ResourceStatus'], "work_start": str(work_start), "work_end": str(work_end)})
            removeTicketIDsFromParameters(opsItemIds)

        else:
            
            #1. create an error ops item  3. update ops items with an error message  4. add work note in item ticket notifying that an error occured.
            createErrorOpsItem(message['StackId'], "Stack did not update correctly.")
            updateOpsItems(opsItemIds, 'InProgress', message['ResourceStatus'])
            updateITSMTickets(opsItemIds, 'update', {"work_notes": message['ResourceStatus']})

        close_window(windowId)
        
        return True
        
    except Exception as error:
        print("Exception caught while handling main stack event.\n" + str(error))
        return False

def removeTagsFromParameter(parameterKey, tagKeys):
    
    try:
        
        response = client.remove_tags_from_resource(
            ResourceType='Parameter',
            ResourceId=parameterKey,
            TagKeys=tagKeys
        )
        
        return True
        
    except Exception as error:
        print("Exception caught while removing tag[" + tagKey + "] from parameter[" + parameterKey + "].\n" + str(error))
        return False

def removeTicketIDsFromParameters(opsItemIds):
    
    try:
        
        client = boto3.client('ssm')
        
        for opsItemId in opsItemIds:
            
            opsItem = getOpsItem(opsItemId['OpsItemId'])
            parameterKey = opsItem['OpsItem']['OperationalData']['parameterKey']['Value']
            removeTagsFromParameter(parameterKey, ['itsmTicketId', 'opsItemId'])
            
        return True
        
    except Exception as error:
        print("Exception caught while updating parameters. \n" + str(error))
        return False

def updateITSMTickets(opsItemIds, function, message):

	try:
		
		client = boto3.client('ssm')
		
		lambdaEvent = {}
		lambdaEvent['function'] = function
		lambdaEvent['serviceNowURL'] = getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
		lambdaEvent['serviceNowUser'] = getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
		lambdaEvent['serviceNowPass'] = getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
		lambdaEvent['densifyURL'] = getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
		lambdaEvent['densifyUser'] = getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
		lambdaEvent['densifyPass'] = getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']

		for key in message:
			lambdaEvent[key] = message[key]

		for opsItemId in opsItemIds:
		
		    opsItem = getOpsItem(opsItemId['OpsItemId'])
		    parameterKey = opsItem['OpsItem']['OperationalData']['parameterKey']['Value']
		    lambdaEvent['ticketId'] = getParameter(parameterKey)['Tags']['itsmTicketId']
		    resp = lambda_execute("Densify-ITSM", lambdaEvent)
            
		    if resp == False:
		    	print("Error while updating ticket with ID[" + lambdaEvent['ticketId'] + "].")

		return True
				
	except Exception as error:
		print("Exception encountered while updating ITSM tickets.\n" + str(error))
		return False    

def updateOpsItems(opsItemIds, status, message):
    
	try:
		
		client = boto3.client('ssm')
		
		for opsItemId in opsItemIds:
			response = client.update_ops_item(
    		    OperationalData={
    		        'executionStatus': {
    		            'Value': message,
    		            'Type': 'String'
    		        }
    		    },
    		    Status=status,
    		    OpsItemId=opsItemId['OpsItemId']
    		)

		return True
				
	except Exception as error:
		print("Exception encountered while updating ops items.\n" + str(error))
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

def process_resource_stackEvent(message):
    
    try:
        
        OpsItemFilters=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-id\",\"value\": \"" + message['StackId'] + "\"}"
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

        client = boto3.client('ssm')
        response = client.describe_ops_items(
            OpsItemFilters=OpsItemFilters
        )
        
        opsItem = False
        for opsItemTmp in response['OpsItemSummaries']:
            if opsItemTmp['OperationalData']['cloudformation:logical-id']['Value'] == message['LogicalResourceId']:
                opsItem = getOpsItem(opsItemTmp['OpsItemId'])        
        
        if opsItem == False:
            raise Exception ("A single opsItem was not located.")
		
        opsItemId = opsItem['OpsItem']['OpsItemId']
        print("OpsItem [" + opsItemId + "] found.")

        eventId = message['ResourceStatus'] + "-" + message['Timestamp']
        if 'stackEvents' in opsItem['OpsItem']['OperationalData']:
            eventId = eventId + "\n" + opsItem['OpsItem']['OperationalData']['stackEvents']['Value']
        
        response = client.update_ops_item(
		    OperationalData={
		        'stackEvents': {
		            'Value': eventId,
		            'Type': 'String'
		        }
		    },
		    OpsItemId=opsItemId
		)
    
        return True
        
    except Exception as error:
        print("Exception encountered while updating opsItem. " + str(error))
        return False

def locateOpsItem(message):
    
    try:
        
        OpsItemFilters=[
			{
				'Key': 'OperationalData',
				'Values': [
					"{\"key\":\"cloudformation:stack-id\",\"value\": \"" + message['StackId'] + "\"}"
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

        client = boto3.client('ssm')
        response = client.describe_ops_items(
            OpsItemFilters=OpsItemFilters
        )
        
        for opsItem in response['OpsItemSummaries']:
            if opsItem['OperationalData']['cloudformation:logical-id']['Value'] == message['LogicalResourceId']:
                return getOpsItem(opsItem['OpsItemId'])
        
        return False
        
    except Exception as error:
        print("Exception encountered while trying to locate ops Item.\n" + str(error))
        return False  

def getOpsItem(OpsItemId):
    
    try:
        
        client = boto3.client('ssm')
        
        response = client.get_ops_item(
            OpsItemId=OpsItemId
        )
        
        return response
        
    except Exception as error:
        print("Exception encountered while getting opsItem [" + OpsItemId + "].\n" + str(error))
        return False
        
def describeOpsItems(filter):
    
    try:

        client = boto3.client('ssm')
        response = client.describe_ops_items(
            OpsItemFilters=filter
        )
        
        print(response)
        
        opItemIds = []
        for opsItem in response['OpsItemSummaries']:
            opItemIds.append({'OpsItemId': opsItem['OpsItemId']})
        
        return opItemIds
        
    except Exception as error:
        print("Exception encountered while describing opsItems.\n" + str(error))
        return False