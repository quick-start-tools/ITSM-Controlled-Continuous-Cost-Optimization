# -*- coding: utf-8 -*-
"""
Created on Wed Aug  5 16:33:55 2020

@author: draveendran
"""


import json
import boto3
import re
import datetime
import ssm_functions
import itsm_adapter

def lambda_handler(event, context):
    # TODO implement
    
    print(event)

    parameterKey = event['detail']['name']
    state = event['detail']['label']

    #validate the request ########################################
    pattern = re.compile(r'^/densify/iaas/(.*)/(.*)/(.*)$')
    mo = pattern.search(parameterKey) 
    
    if (mo == None or mo != None and ((mo.group(1) != 'ec2' and mo.group(1) != 'rds') and (mo.group(3) != 'instanceType' and mo.group(3) != 'dbInstanceClass'))):
        print("Request is not for an EC2 or RDS recommendation.  Not proceeding.")
        return
    
    parameter = {}
    parameter['Parameter'] = ssm_functions.getParameter(parameterKey)['Parameter']
    parameter['Tags'] = ssm_functions.list_tags('Parameter', parameterKey)
    
    if 'cloudformation:stack-name' not in parameter['Tags']:
        print("This resource does not belong to a CFT.  Not proceeding.")
        return

    #Execute request #############################################
    if state == 'Initialize':
        
        print("Request is intialized, proceed to open an ITSM ticket.")
        
        resp = itsm_adapter.executeFunction("open", recommendation=parameter['Tags'])
        if resp != False:
            ssm_functions.addTagsToResource('Parameter', parameterKey, [{'Key': 'itsmTicketId', 'Value': resp['ticketId']}])
        else:
            print("Failed to create ticket.")
            
    elif state == 'Approved':

        print("Request is approved, creating new ops ticket.")
        
        opsItemId = createOpsItem(parameter)
        if opsItemId != False:
            ssm_functions.addTagsToResource('Parameter', parameterKey, [{'Key': 'opsItemId', 'Value': opsItemId}])
            
    elif state == 'Scheduled':
        
        print("Request is scheduled for execution.  Updating ITSM Ticket.")
        
        maintenanceWindow = ssm_functions.findActiveMaintenanceWindow("mw-" + parameter['Tags']['cloudformation:stack-name'])
        start_date = datetime.datetime.strptime(str(maintenanceWindow['Schedule'])[3:-1], '%Y-%m-%dT%H:%M:%S')
        end_date = start_date + datetime.timedelta(hours=int(maintenanceWindow['Duration']))
        
        input = {}
        input['start_date'] = str(start_date)
        input['end_date'] = str(end_date)
        input['state'] = "-1"
        
        resp = itsm_adapter.executeFunction("schedule", ticketId=parameter['Tags']['itsmTicketId'], input=input)
                
        if resp == False:
            print("Error while updating ticket with ID[" + str(parameter['Tags']['itsmTicketId']) + "].")
            
    elif state == 'Executed':
        
        print("Insight has been executed.  Updating ITSM Ticket.")
        
        opsItem = ssm_functions.getOpsItem(parameter['Tags']['opsItemId'])
        work_notes = json.loads(opsItem['OpsItem']['OperationalData']['executionStatus']['Value'])
        
        input = {}
        input['work_start'] = work_notes['work_start']
        input['work_end'] = work_notes['work_end']
        input['state'] = "0"
        
        resp = itsm_adapter.executeFunction("close", ticketId=parameter['Tags']['itsmTicketId'], input=input)
                
        if resp == False:
            print("Error while updating ticket with ID[" + lambdaEvent['ticketId'] + "].")   
            
    elif state == 'Closed':
        
        print("Insight has been closed.  Closing Ops Item.")
        
        ssm_functions.updateOpsItems([parameter['Tags']['opsItemId']], 'Resolved')
        ssm_functions.deleteMaintenanceWindow(ssm_functions.findActiveMaintenanceWindow("mw-" + parameter['Tags']['cloudformation:stack-name'])['WindowId'])
        ssm_functions.removeTagsFromResource('Parameter', parameterKey, ['opsItemId', 'ITSMTicketId'])

    return {
        'statusCode': 200,
        'body': json.dumps('Execution Completed Sucessfully!')
    }

def lambda_execute(functionName, eventObj):
    
    try:
                
        eventObj['serviceNowURL'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
        eventObj['serviceNowUser'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
        eventObj['serviceNowPass'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
        eventObj['densifyURL'] = ssm_functions.getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
        eventObj['densifyUser'] = ssm_functions.getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
        eventObj['densifyPass'] = ssm_functions.getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']        
        
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

def createOpsItem(parameter):

    try:

        if ssm_functions.findActiveOpsItem(parameter['Parameter']['Name']) != False:
            print("Ops ticket already exists.  Not proceeding.")
            return

        #Generate ARN of the resource
        if parameter['Tags']['serviceType'] == 'EC2':
            serviceArn = 'arn:aws:ec2:' + parameter['Tags']['regionId'] + ':' + parameter['Tags']['accountIdRef'] + ':instance/' + parameter['Tags']['resourceId']
        elif parameter['Tags']['serviceType'] == 'RDS':
            serviceArn = 'arn:aws:rds:' + parameter['Tags']['regionId'] + ':' + parameter['Tags']['accountIdRef'] + ':db:' + parameter['Tags']['name']  
            
        densifyUrl = ssm_functions.getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']

        opsData = {}
        opsData['serviceType'] = {}
        opsData['serviceType']['Value'] = parameter['Tags']['serviceType']
        opsData['serviceType']['Type'] = 'String'
        opsData['resourceId'] = {}
        opsData['resourceId']['Value'] = parameter['Tags']['resourceId']
        opsData['resourceId']['Type'] = 'SearchableString'
        opsData['cloudformation:stack-name'] = {}
        opsData['cloudformation:stack-name']['Value'] = parameter['Tags']['cloudformation:stack-name']
        opsData['cloudformation:stack-name']['Type'] = 'SearchableString'
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
                    "{\"key\":\"cloudformation:stack-name\",\"value\":\"" + parameter['Tags']['cloudformation:stack-name'] + "\"}",
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

        relatedOpsItems = []
        for opsItemId in ssm_functions.listAllOpsItemIds(OpsItemFilters):
            relatedOpsItems.append({'OpsItemId': opsItemId})

        print("Successfully identified all related ops items: " + str(relatedOpsItems))
        
        category = 'Cost' if float(parameter['Tags']['savingsEstimate']) >= float(0) else 'Performance'
        severity = '2' if float(parameter['Tags']['savingsEstimate']) >= float(0) else '1'
        opsItemID = ssm_functions.createOpsItem('Maintainence Window Request', 'Densify', 'MW Request [' + parameter['Tags']['name'] + ']', relatedOpsItems=relatedOpsItems, opsData=opsData, category=category, severity=severity)
        
        if opsItemID == False:
            raise Exception ("Failed to create ops ticket.")
        
        print('Successfully created ops ticket: ' + opsItemID)
        
        if len(relatedOpsItems) > 0:
            existingOpsItem = ssm_functions.getOpsItem(relatedOpsItems[0]['OpsItemId'])
            if existingOpsItem['OpsItem']['Status'] == 'InProgress' and 'scheduledMaintenanceWindowDetails' in existingOpsItem['OpsItem']['OperationalData']:
                print("A maintenance window has already been scheduled for this CF stack.  Updating the opsItem with existing window ID.")
                opsData = {}
                opsData['scheduledMaintenanceWindowDetails'] = {}
                opsData['scheduledMaintenanceWindowDetails']['Value'] = existingOpsItem['OpsItem']['OperationalData']['scheduledMaintenanceWindowDetails']['Value']
                opsData['scheduledMaintenanceWindowDetails']['Type'] = 'String'
                ssm_functions.updateOpsItems([opsItemID], 'InProgress', opsData=opsData)

            print("Updating all related opsItems.")
            for opsItem in relatedOpsItems:
                relOpsItem = []
                relOpsItem = relatedOpsItems.copy()
                relOpsItem.append({'OpsItemId': opsItemID})
                relOpsItem.remove({'OpsItemId': opsItem['OpsItemId']})
                ssm_functions.setRelatedOpsItem(opsItem['OpsItemId'], relOpsItem)
        
        return opsItemID
        
    except Exception as error:
        print("Exception caught while trying to create an opsItem. \n" + str(error))
        return False