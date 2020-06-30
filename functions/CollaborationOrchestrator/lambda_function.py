import json
import boto3
import re
import datetime
import time

def lambda_handler(event, context):
    # TODO implement


    client = boto3.client('ssm')
    parameterKey = event['detail']['name']

    #validate the request
    pattern = re.compile(r'^/densify/iaas/(.*)/(.*)/(.*)$')
    mo = pattern.search(parameterKey) 
    
    if (mo == None or mo != None and ((mo.group(1) != 'ec2' and mo.group(1) != 'rds') and (mo.group(3) != 'instanceType' and mo.group(3) != 'dbInstanceClass'))):
        print("Request is not for an EC2 or RDS recommendation.  Not proceeding.")
        return
    
    parameter = getParameter(parameterKey)
    
    if 'cloudformation:stack-name' not in parameter['Tags']:
        print("This resource does not belong to a CFT.  Not proceeding.")
        return

    #Execute request
    opsItems = findActiveOpsItem(parameterKey)
    if len(opsItems) == 1:

        print("A maintenance window request already exists.  Printing details.")
        print(opsItems[0])

        #Recommendation can only be in the intilized or Reversed state.
        #In either case, remove the existing MW request.
        print("Recommendation in the '" + event['detail']['label'] + "' state.  Closing the existing maintenance window request.")
        removeOpsItem(opsItems[0]['OpsItemId'])

        if opsItems[0]['Status'] == 'InProgress':
            print("Cancel scheduled maintenance window if no other resource requires an update.")
            cancelWindowIfNoOpsItemsExists(opsItems[0]['OpsItemId'], parameter)

    elif len(opsItems) == 0:
        
        print("There are no active maintenance windows.")

        if event['detail']['label'] == 'Initialize':
            print("Recommendation initialized.  Create ServiceNow approval request.")

            lambdaEvent = {}
            lambdaEvent['function'] = 'open'
            lambdaEvent['recommendation'] = parameter['Tags']
            lambdaEvent['serviceNowURL'] = getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
            lambdaEvent['serviceNowUser'] = getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
            lambdaEvent['serviceNowPass'] = getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
            lambdaEvent['densifyURL'] = getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
            lambdaEvent['densifyUser'] = getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
            lambdaEvent['densifyPass'] = getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']

            resp = lambda_execute("Densify-ITSM", lambdaEvent)
            if resp != False:
                ssm_addTagsToResource('Parameter', parameterKey, [{'Key': 'itsmTicketId', 'Value': str(json.loads(resp)['ticketId'])}])
            else:
                print("Failed to create ticket.")
                
        else:
            print("Recommendation '" + event['detail']['label'] + "', creating new maintenance window request.")
            opsItemId = createOpsItem(parameter)
            if opsItemId != False:
                ssm_addTagsToResource('Parameter', parameterKey, [{'Key': 'opsItemId', 'Value': opsItemId}])

    return {
        'statusCode': 200,
        'body': json.dumps('Execution Completed Sucessfully!')
    }

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

def ssm_addTagsToResource(resourceType, resourceId, tags):

    try:
    
        client = boto3.client('ssm')
    
        response = client.add_tags_to_resource(
            ResourceType=resourceType,
            ResourceId=resourceId,
            Tags=tags
        )
        
        return True
    
    except Exception as error:
        print("Error encountered while adding tags to " + resourceType + " with ID[" + resourceId + "]")
        print(error)
        return True

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

def findActiveOpsItem(parameterKey):
    
    try:
        
        filter=[
            {
                'Key': 'OperationalData',
                'Values': [
                    "{\'key\':\'parameterKey\',\'value\':\'" + parameterKey + "\'}"
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
            OpsItemFilters=filter
        )
        
        return response['OpsItemSummaries']
        
    except Exception as error:
        print(error)

def findInactiveOpsItem(parameterKey):
    
    try:
        
        filter=[
            {
                'Key': 'OperationalData',
                'Values': [
                    "{\'key\':\'parameterKey\',\'value\':\'" + parameterKey + "\'}"
                ],
                'Operator': 'Equal'
            },
            {
                'Key': 'Status',
                'Values': [
                    "Resolved"
                ],
                'Operator': 'Equal'
            }
        ]
        
        client = boto3.client('ssm')
        opsItems = client.describe_ops_items(
            OpsItemFilters=filter
        )

        return opsItems['OpsItemSummaries']
        
    except Exception as error:
        print(error)
        
def createOpsItem(parameter):

    try:

        if findActiveOpsItem(parameter['Parameter']['Name']) != []:
            print("Maintainence window request already exists.  Not proceeding.")
            return

        #Generate ARN of the resource
        if parameter['Tags']['serviceType'] == 'EC2':
            serviceArn = 'arn:aws:ec2:' + parameter['Tags']['regionId'] + ':' + parameter['Tags']['accountIdRef'] + ':instance/' + parameter['Tags']['resourceId']
        elif parameter['Tags']['serviceType'] == 'RDS':
            serviceArn = 'arn:aws:rds:' + parameter['Tags']['regionId'] + ':' + parameter['Tags']['accountIdRef'] + ':db:' + parameter['Tags']['name']  
            
        densifyUrl = getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
        
        opsData = {}
        opsData['serviceType'] = {}
        opsData['serviceType']['Value'] = parameter['Tags']['serviceType']
        opsData['serviceType']['Type'] = 'String'
        opsData['resourceId'] = {}
        opsData['resourceId']['Value'] = parameter['Tags']['resourceId']
        opsData['resourceId']['Type'] = 'SearchableString'
        opsData['cloudformation:stack-name'] = {}
        opsData['cloudformation:stack-name']['Value'] = parameter['Tags']['cloudformation:stack-name']
        opsData['cloudformation:stack-name']['Type'] = 'String'
        opsData['cloudformation:logical-id'] = {}
        opsData['cloudformation:logical-id']['Value'] = parameter['Tags']['cloudformation:logical-id']
        opsData['cloudformation:logical-id']['Type'] = 'SearchableString'
        opsData['cloudformation:stack-id'] = {}
        opsData['cloudformation:stack-id']['Value'] = parameter['Tags']['cloudformation:stack-id']
        opsData['cloudformation:stack-id']['Type'] = 'SearchableString'
        opsData['densifyEntityId'] = {}
        opsData['densifyEntityId']['Value'] = parameter['Tags']['entityId']
        opsData['densifyEntityId']['Type'] = 'String'
        opsData['name'] = {}
        opsData['name']['Value'] = parameter['Tags']['name']
        opsData['name']['Type'] = 'String'
        opsData['analysisReportURL'] = {}
        opsData['analysisReportURL']['Value'] = densifyUrl + '/CIRBA/api/v2' + parameter['Tags']['rptHref']
        opsData['analysisReportURL']['Type'] = 'String'
        opsData['densifyURL'] = {}
        opsData['densifyURL']['Value'] = densifyUrl
        opsData['densifyURL']['Type'] = 'String'
        opsData['parameterKey'] = {}
        opsData['parameterKey']['Value'] = parameter['Parameter']['Name']
        opsData['parameterKey']['Type'] = 'SearchableString'
        
        opsData['/aws/resources'] = {}
        opsData['/aws/resources']['Value'] = "[{\"arn\": \"" + parameter['Tags']['cloudformation:stack-id'] + "\"}, {\"arn\": \"" + parameter['Parameter']['ARN'] + "\"}, {\"arn\": \"" + serviceArn + "\"}]"
        opsData['/aws/resources']['Type'] = 'SearchableString'

        opsData['/aws/automations'] = {}
        opsData['/aws/automations']['Value'] = "[{\"automationId\": \"ScheduleMaintenanceWindow\", \"automationType\": \"AWS::SSM::Automation\"}]"
        opsData['/aws/automations']['Type'] = 'SearchableString'

        OpsItemFilters=[
            {
                'Key': 'OperationalData',
                'Values': [
                    "{\"key\":\"cloudformation:stack-id\",\"value\":\"" + parameter['Tags']['cloudformation:stack-id'] + "\"}",
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
        print("Related Ops Items: " + str(relatedOpsItems))
        
        client = boto3.client('ssm')
        
        response = client.create_ops_item(
            Description='Maintainence Window Request',
            OperationalData=opsData,
            RelatedOpsItems=relatedOpsItems,
            Source='Densify',
            Title='MW Request [' + parameter['Tags']['name'] + ']',
            Category='Cost' if float(parameter['Tags']['savingsEstimate']) >= float(0) else 'Performance',
            Severity='2' if float(parameter['Tags']['savingsEstimate']) >= float(0) else '1'
        )
        
        opsItemID = response['OpsItemId']
        
        print('Maintainence window request created.')
        print(response)

        if len(relatedOpsItems) > 0:
            existingOpsItem = client.get_ops_item(
                OpsItemId=relatedOpsItems[0]['OpsItemId']
            )
            if existingOpsItem['OpsItem']['Status'] == 'InProgress' and 'scheduledMaintenanceWindowDetails' in existingOpsItem['OpsItem']['OperationalData']:
                print("A maintenance window has already been scheduled for this CF stack.  Updating the opsItem with existing window ID.")
                opsData = {}
                opsData['scheduledMaintenanceWindowDetails'] = {}
                opsData['scheduledMaintenanceWindowDetails']['Value'] = existingOpsItem['OpsItem']['OperationalData']['scheduledMaintenanceWindowDetails']['Value']
                opsData['scheduledMaintenanceWindowDetails']['Type'] = 'String'
                response = client.update_ops_item(
                    Status='InProgress',
                    OperationalData=opsData,
                    OpsItemId=opsItemID
                )

            print("Updating all related opsItems.")
            for opsItem in relatedOpsItems:
                relOpsItem = []
                relOpsItem = relatedOpsItems.copy()
                relOpsItem.append({'OpsItemId': opsItemID})
                relOpsItem.remove({'OpsItemId': opsItem['OpsItemId']})
                response = client.update_ops_item(
                    RelatedOpsItems=relOpsItem,
                    OpsItemId=opsItem['OpsItemId']
                )
        
        return opsItemID
        
    except Exception as error:
        print("Exception caught while trying to create an opsItem. \n" + str(error))
        return False

def removeOpsItem(opsItemId):
    
    try:

        client = boto3.client('ssm')
        
        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )
        
        stackId = opsItem['OpsItem']['OperationalData']['cloudformation:stack-id']['Value']
        
        response = client.update_ops_item(
            Status='Resolved',
            OpsItemId=opsItemId
        )
        
        print(response)
        time.sleep(10)

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
        print(relatedOpsItems)

        print("Updating all related opsItems.")
        for opsItem in relatedOpsItems:
            relOpsItem = []
            relOpsItem = relatedOpsItems.copy()
            relOpsItem.remove({'OpsItemId': opsItem['OpsItemId']})
            response = client.update_ops_item(
                RelatedOpsItems=relOpsItem,
                OpsItemId=opsItem['OpsItemId']
            )

        print("Maintenance window request(s) cancelled.")
        
    except Exception as error:
        print(error)

def cancelWindowIfNoOpsItemsExists(opsItemId, parameter):
    
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
        
        if len(relatedOpsItems) == 0:
            print("Maintenance window is not assoicated with any other opsItems.  Deleting window.")
            client.delete_maintenance_window(
                WindowId=getExistingMaintenanceWindow(opsItemId)
            )

    except Exception as error:
        print(error)
        
def getExistingMaintenanceWindow(opsItemId):
    
    try:
        
        client = boto3.client("ssm")
        
        opsItem = client.get_ops_item(
            OpsItemId=opsItemId
        )
        
        windowName = "mw-" + opsItem['OpsItem']['OperationalData']['cloudformation:stack-name']['Value']

        response = client.describe_maintenance_windows(
            Filters=[
                {
                    'Key': 'Name',
                    'Values': [
                        windowName,
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

        if len(response['WindowIdentities']) > 0:
            return response['WindowIdentities'][0]['WindowId']
        
        return None
        
    except Exception as error:
        print(error)