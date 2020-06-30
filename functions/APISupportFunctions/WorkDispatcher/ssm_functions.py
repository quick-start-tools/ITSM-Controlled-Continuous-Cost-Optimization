import boto3
import time

def list_tags(resourceType, resourceId, region):
	
	ssm_client = boto3.client('ssm', region)

	try:

		response = ssm_client.list_tags_for_resource(
            ResourceType=resourceType,
            ResourceId=resourceId
        )

		returnJson = {}
		for tag in response['TagList']:
			returnJson[tag['Key']] = tag['Value']
		
		print("Return taglist [" + str(returnJson) + "].")
		return returnJson
		
	except Exception as error:
	    print("Exception caught during parameter retreival for parameter[" + resourceId + "] in region[" + region + "]: " + str(error))
	    return False
		
def getParameter(key, region):
	
	ssm_client = boto3.client('ssm', region)

	try:
		
		response = ssm_client.get_parameter(
			Name=key,
			WithDecryption=True
		)
		
		return response	
		
	except Exception as error:
		print("Exception caught during parameter retreival for parameter[" + key + "] in region[" + region + "]: " + str(error))
		return False
		
def getParameterCurrentLabels(key, region):

	ssm_client = boto3.client('ssm', region)

	try:
	    
	    currentVersion = getParameter(key, region)['Parameter']['Version']
		
	    response = ssm_client.get_parameter_history(
            Name=key,
            WithDecryption=True
        )
        
	    for parameter in response['Parameters']:
	    	if parameter['Version'] == currentVersion:
	    		return parameter['Labels']
		
	    return False
		
	except Exception as error:
		print("Exception caught during parameter retreival for parameter[" + key + "] in region[" + region + "]: " + str(error))
		return False

def labelParameterVersion(parameterKey, version, labels, region):
	
	ssm_client = boto3.client('ssm', region)

	try:
		
		response = ssm_client.label_parameter_version(
            Name=parameterKey,
            ParameterVersion=version,
            Labels=labels
        )

		return True
		
	except Exception as error:
		print("Exception caught while labeling parameter[" + parameterKey + "] in region[" + region + "]: " + str(error))
		return False

def putParameter(parameterKey, value, description, region):
	
	ssm_client = boto3.client('ssm', region)

	try:
		
		response = ssm_client.put_parameter(
            Name=parameterKey,
            Description=description,
            Value=value,
            Type='String',
            Overwrite=True,
            Tier='Standard'
        )
        
		#time.sleep(0.01)
		    
		return response['Version']
		
	except Exception as error:
		print("Exception caught while creating/updating parameter[" + parameterKey + "] in region[" + region + "]: " + str(error))
		return False

def addTagsToResource(resourceType, resourceId, tags, region):

    try:
    
        client = boto3.client('ssm', region)
        response = client.add_tags_to_resource(
            ResourceType=resourceType,
            ResourceId=resourceId,
            Tags=tags
        )

        return True
    
    except Exception as error:
        print("Error encountered while adding tags to " + resourceType + " with ID[" + resourceId + "]: " + str(error))
        return False

def removeTagsFromResource(resourceType, resourceId, tags):

    try:
    
        client = boto3.client('ssm')
    
        response = client.remove_tags_from_resource(
            ResourceType=resourceType,
            ResourceId=resourceId,
            Tags=tags
        )
        
        return True
    
    except Exception as error:
        print("Error encountered while removing tags from " + resourceType + " with ID[" + resourceId + "]: " + str(error))
        return False
        
def listAllOpsItemIds(filter):
    
    try:
        
        client = boto3.client('ssm')
        
        response = client.describe_ops_items(
            OpsItemFilters=filter
        )
        
        opItemIds = []
        for opsItem in response['OpsItemSummaries']:
            opItemIds.append(opsItem['OpsItemId'])
        
        return opItemIds
        
    except Exception as error:
        print("Exception caught while trying to list ops item ids: " + str(error))
        return False

def getOpsItem(OpsItemId):
    
    try:
        
        client = boto3.client('ssm')
        
        response = client.get_ops_item(
            OpsItemId=OpsItemId
        )
        
        return response
        
    except Exception as error:
        print("Exception encountered while getting opsItem [" + OpsItemId + "]: " + str(error))
        return False
        
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
        
        if len(response['OpsItemSummaries']) != 1:
        	return False
        	
        return getOpsItem(response['OpsItemSummaries'][0]['OpsItemId'])
        
    except Exception as error:
        print("Exception caught while trying to identify active ops item: " + str(error))
        return False
        
def close_window(windowId):
	
	try:
		
		client = boto3.client('ssm')
		
		response = client.delete_maintenance_window(
		    WindowId=windowId
		)
		
		return True
				
	except Exception as error:
		print("Exception caught while trying to close maintenance window [" + windowId + "]: " + str(error))
		return False

def updateOpsItems(opsItemIds, status):
    
	try:
		
		client = boto3.client('ssm')
		
		for opsItemId in opsItemIds:
			response = client.update_ops_item(
    		    Status=status,
    		    OpsItemId=opsItemId
    		)

		return True
				
	except Exception as error:
		print("Exception encountered while updating ops items: " + str(error))
		return False
		
def removeFromRelatedOpsItem(targetOpsItemId, opsItemIdToRemove):
    
	try:
		
		client = boto3.client('ssm')
		
		targetOpsItem = getOpsItem(targetOpsItemId)
		newRelatedList = []
		for opsItemId in targetOpsItem:
			if opsItemId['OpsItemId'] != opsItemIdToRemove:
				newRelatedList.append({'OpsItemId': opsItemId['OpsItemId']})
                
		response = client.update_ops_item(
		    RelatedOpsItems=newRelatedList,
		    OpsItemId=targetOpsItemId
		)

		return True
				
	except Exception as error:
		print("Exception encountered while removing from related ops item ids: " + str(error))
		return False