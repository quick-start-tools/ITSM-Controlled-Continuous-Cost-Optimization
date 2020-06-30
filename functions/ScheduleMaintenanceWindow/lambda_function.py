import json
import boto3
import datetime
import time
import ssm_functions

def lambda_handler(event, context):
    # TODO implement
    
    try:
        
        print("Incoming event: " + str(event))
        
        #Validate Event Object
        #start_date = datetime.datetime.strptime(event['cronExpression'], '%Y-%m-%dT%H:%M:%S')
        #if start_date < datetime.datetime.now():
        #    raise Exception ('Please specify a future dated cronExpression in the ISO 8601 format.')

        if int(event['duration']) < 1 or int(event['duration']) > 24:
            raise Exception ("Duration can only be between 1-24 hours.  Specify as an integer.")
        
        opsItemId = event['opsItemId']
        windowId = getExistingMaintenanceWindow(opsItemId)
    
        if windowId != None:
            print("Updating existing maintenance window.")
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
        
        print("Updating all assoicated ITSM tickets.")
        updateITSMTickets(opsItemId, event)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Hello from Lambda!')
        }
    
    except Exception as error:
        print("Exception encountered: " + str(error))
        return {'statusCode': -1, 'body': json.dumps({'message': str(error)})}

def updateITSMTickets(opsItemId, event):
    
    try:
        
        client = boto3.client('ssm')

        relatedOpsItems = getRelatedOpsItems(opsItemId)
        
        datetime_object = datetime.datetime.strptime(event['cronExpression'], '%Y-%m-%dT%H:%M:%S')

        for opsItem in relatedOpsItems:
            
            response = client.get_ops_item(
                OpsItemId=opsItem['OpsItemId']
            )
            
            parameterKey = response['OpsItem']['OperationalData']['parameterKey']['Value']
            start_date = datetime.datetime.strptime(event['cronExpression'], '%Y-%m-%dT%H:%M:%S')
            end_date = start_date + datetime.timedelta(hours=int(event['duration']))
            
            lambdaEvent = {}
            lambdaEvent['function'] = 'schedule'
            lambdaEvent['ticketId'] = getParameter(parameterKey)['Tags']['itsmTicketId']
            lambdaEvent['start_date'] = str(start_date)
            lambdaEvent['end_date'] = str(end_date)
            lambdaEvent['serviceNowURL'] = getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
            lambdaEvent['serviceNowUser'] = getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
            lambdaEvent['serviceNowPass'] = getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
            lambdaEvent['densifyURL'] = getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
            lambdaEvent['densifyUser'] = getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
            lambdaEvent['densifyPass'] = getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']

            resp = lambda_execute("Densify-ITSM", lambdaEvent)
            
            if resp == False:
                print("Error while updating ticket with ID[" + lambdaEvent['ticketId'] + "].")
        
        return True

    except Exception as error:
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
        statusCode = int(payload['statusCode'])
        body = payload['body']
        
        print("Lambda executed with return code: " + str(statusCode) + " and payload: " + str(body))
        if statusCode != 200:
        	raise Exception(str(body))
        
        return body
        
    except Exception as error:
        print("Error encountered while executing lambda[" + functionName + "].")
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
        jsonStr = json.dumps(payload)
        
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
            TaskArn='arn:aws:lambda:us-east-1:725336635610:function:ExecutionStage1',
            ServiceRoleArn='arn:aws:iam::725336635610:role/automationDoc',
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

        response = client.add_tags_to_resource(
            ResourceType='MaintenanceWindow',
            ResourceId=windowId,
            Tags=[
                {
                    'Key': 'cloudformation:stack-id',
                    'Value': stackId                  
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

def getExistingMaintenanceWindow(opsItemId):
    
    try:
        
        client = boto3.client("ssm")
        
        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )
        
        if 'scheduledMaintenanceWindowDetails' in opsItem['OpsItem']['OperationalData']:
            return opsItem['OpsItem']['OperationalData']['scheduledMaintenanceWindowDetails']['Value'].split("\n")[0].split("=")[1]
        
        return None
        
    except Exception as error:
        print(error)