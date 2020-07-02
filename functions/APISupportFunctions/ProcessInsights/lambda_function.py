import json
import os
import boto3
import ssm_functions
import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
import logging

logger = logging.getLogger()
logger.setLevel(logging.WARNING)

def lambda_handler(event, context):
    
    print(event)
    insights = event
        
    print("Processing insights for CFT " + insights[0]['cloudformation:stack-id'])

    #process insights
    executor = ThreadPoolExecutor(max_workers=int(os.environ['ThreadPoolSize']))
    futures = []
    for insight in insights:

        if insight['serviceType'] == 'EC2':
            args = ['/densify/iaas/ec2/' + insight['resourceId'] + '/instanceType', insight]
            futures.append(executor.submit(processInsight, args))
        elif insight['serviceType'] == 'RDS':
            args = ['/densify/iaas/rds/' + insight['name'] + '/dbInstanceClass', insight]
            futures.append(executor.submit(processInsight, args))

    result = wait(futures, timeout=900)
    print('Completed Tasks : '+str(result.done))
    
    time.sleep(5)
    
    #fix any remaining ops items
    filter=[
        {
            'Key': 'OperationalData',
            'Values': [
                "{\'key\':\'cloudformation:stack-id\',\'value\':\'" + insights[0]['cloudformation:stack-id'] + "\'}"
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
    
    opsItemIds = ssm_functions.listAllOpsItemIds(filter, region=insights[0]['regionId'])
    if len(opsItemIds) != 0:
        print("Adjusting related ops items for remaining ops items " + str(opsItemIds) + ".")
        for opsItemId in opsItemIds:
            relatedOpsItems = []
            relatedOpsItemIds = opsItemIds.copy()
            counter = 0
            for relatedOpsItemId in relatedOpsItemIds:
                if relatedOpsItemId == opsItemId:
                    del relatedOpsItemIds[counter]
                    break
                else:
                    counter+=1
            for relatedOpsItemId in relatedOpsItemIds:
                relatedOpsItems.append({'OpsItemId': relatedOpsItemId})
            ssm_functions.setRelatedOpsItem(opsItemId, relatedOpsItems, region=insights[0]['regionId'])

    else:
        maintenanceWindowId = ssm_functions.findActiveMaintenanceWindow('mw-' + insights[0]['cloudformation:stack-name'], region=insights[0]['regionId'])
        if maintenanceWindowId != False:
            print("Cancelling maintenance window [" + str(maintenanceWindowId) + "].")
            ssm_functions.close_window(maintenanceWindowId, region=insights[0]['regionId'])

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed insights!')
    }

def hasInsightChanged(current, new):
    
    try:
        
        tagChanged = False
        recommendationChanged = False
        if current != {}:
            for key in new:
                if key != 'currentType' and key != 'recommendedType':

                    if key not in current:
                        tagChanged = True
                        break
                    if key in current and str(new[key]) != str(current[key]):
                        tagChanged = True
                        break                        
           
            if current['currentType'] != new['currentType'] or current['recommendedType'] != new['recommendedType']:
                recommendationChanged = True
        else:
            tagChanged = True
            recommendationChanged = True
        
        return {'hasInsightChanged': recommendationChanged, 'hasTagsChanged': tagChanged}

    except Exception as error:
        print("Exception caught while checking if insight has changed: " + str(error))
        return False

def dictToTagList(pythonDict):
    
    try:
        
        tags = []
        for key in pythonDict:
            tags.append({'Key': key, 'Value': str(pythonDict[key])})        
        
        return tags
        
    except Exception as error:
        print("Exception caught while converting a simple json string [" + str(pythonDict) + "] into a tagList: " + str(error))
        return False

def processInsight(args):

    try:
        
        parameterKey = args[0]
        insight = args[1]
        
        print("Processing insight: " + str(insight))
        
        region = insight['regionId']

        current_parameter = ssm_functions.getParameter(parameterKey, region=region)

        initializeInsight = False
        itsmTicketId = ""
        opsItemId = ""
        opsItem = None
        tags = {}
        
        if current_parameter != False: #parameter already exists
        
            print("Parameter[" + parameterKey + "] currently exists: " + str(current_parameter))

            tags = ssm_functions.list_tags('Parameter', parameterKey, region=region)
            hasChanged = hasInsightChanged(tags, insight)
            
            print(hasChanged)
            if hasChanged['hasInsightChanged'] == False and hasChanged['hasTagsChanged'] == False:
                print("There has been no change to the insight context.  Not doing anything.")
                return True

            if 'itsmTicketId' in tags:
                print("ITSM ticket found: " + str(tags['itsmTicketId']))
                itsmTicketId = tags['itsmTicketId']
            else:
                print("Could not find an assoicated ITSM ticket.")
                
            if 'opsItemId' in tags:
                print("Ops Item found: " + str(tags['opsItemId']))
                opsItemId = tags['opsItemId']
            else:
                print("Could not find an assoicated ops item.")

            if hasChanged['hasInsightChanged'] == True:
                if opsItemId != "":
                    opsItem = ssm_functions.getOpsItem(opsItemId, region=region)
                    if 'scheduledMaintenanceWindowDetails' in opsItem['OpsItem']['OperationalData']:
                        windowDate = datetime.datetime.strptime(opsItem['OpsItem']['OperationalData']['scheduledMaintenanceWindowDetails'].split("\n")[1].split("=")[1], '%Y-%m-%dT%H:%M:%S')
                        timeDelta = windowDate - datetime.utcnow()
                        if timeDelta.total_seconds() > os.environ['CancellationThreshold']:
                            print("Maintenance window is currently scheduled for " + str(windowDate) + " which is more than " + os.environ['CancellationThreshold'] + " seconds away.")
                            initializeInsight = True
                        else:
                            print("Maintenance window is currently scheduled for " + str(windowDate) + " which is less than " + os.environ['CancellationThreshold'] + " seconds away.")
                    else:
                        print("Maintenance window has not yet been scheduled.  Cancelling assoicated ops item and itsm ticket.")
                        initializeInsight = True
                else:
                    initializeInsight = True

            if initializeInsight == False and hasChanged['hasTagsChanged'] == True:
                print("Sychronizing tags")
                ssm_functions.addTagsToResource('Parameter', parameterKey, dictToTagList(insight), region=region)

        else:
            
            print("Parameter[" + parameterKey + "] does not exist.")
            initializeInsight = True
            
        if initializeInsight == True:
            
            if current_parameter != False:
                
                if opsItemId != "":
                    print("Closing Ops Item [" + opsItemId + "].")
                    ssm_functions.updateOpsItems([opsItemId], 'Resolved', region=region)
                
                if itsmTicketId != "":
                    print("Cancelling ITSM ticket [" + itsmTicketId + "].")
                    
                    lambdaEvent = {}
                    lambdaEvent['function'] = 'cancel'
                    lambdaEvent['work_notes'] = 'Cancelling ticket due to new recommendation from Densify.'
                    lambdaEvent['serviceNowURL'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
                    lambdaEvent['serviceNowUser'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
                    lambdaEvent['serviceNowPass'] = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
                    lambdaEvent['densifyURL'] = ssm_functions.getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
                    lambdaEvent['densifyUser'] = ssm_functions.getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
                    lambdaEvent['densifyPass'] = ssm_functions.getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']
                    
                    lambda_execute("Densify-ITSM", lambdaEvent)

            print("Initializing parameter [" + parameterKey + "].")

            if tags != {}:
                tagsToRemove = []
                for tagKey in tags:
                    tagsToRemove.append(tagKey)
                ssm_functions.removeTagsFromResource('Parameter', parameterKey, tagsToRemove, region=region)
            
            print("Updating Parameter")
            version = ssm_functions.putParameter(parameterKey, insight['currentType'], description=insight['name'], region=region)

            if version != False and ssm_functions.addTagsToResource('Parameter', parameterKey, dictToTagList(insight), region=region) == True and ssm_functions.labelParameterVersion(parameterKey, version, ['Initialize'], region=region) == True:
                print("Successfully initialized parameter.")
            
        return True
        
    except Exception as error:
        print("Exception caught while processing " + insight['serviceType'] + " insight.\n" + str(error))
        return False

def lambda_execute(functionName, lambdaEvent):
    
    try:
        
        session = boto3.session.Session()
        client = session.client('lambda')
                    
        response = client.invoke(
            FunctionName=functionName,
            InvocationType='Event',
            Payload=json.dumps(lambdaEvent).encode('utf-8')
        )
        
        print(response)     
        
    except Exception as error:
        print("Exception encountered while dispatching job: " + str(error))
        return False