import boto3
import os

def list_tags(resourceType, resourceId, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)

    try:

        response = ssm_client.list_tags_for_resource(
            ResourceType=resourceType,
            ResourceId=resourceId
        )

        returnJson = {}
        for tag in response['TagList']:
            returnJson[tag['Key']] = tag['Value']

        return returnJson

    except Exception as error:
        print("Exception caught during parameter retreival for parameter[" + resourceId + "] in region[" + region + "]: " + str(error))
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

def getParameterCurrentLabels(key, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        currentVersion = getParameter(key, region=region)['Parameter']['Version']

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

def addTagsToResource(resourceType, resourceId, tags, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        ssm_client.add_tags_to_resource(
            ResourceType=resourceType,
            ResourceId=resourceId,
            Tags=tags
        )

        return True

    except Exception as error:
        print("Error encountered while adding tags to " + resourceType + " with ID[" + resourceId + "]: " + str(error))
        return False

def removeTagsFromResource(resourceType, resourceId, tags, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        ssm_client.remove_tags_from_resource(
            ResourceType=resourceType,
            ResourceId=resourceId,
            TagKeys=tags
        )

        return True

    except Exception as error:
        print("Error encountered while removing tags from " + resourceType + " with ID[" + resourceId + "]: " + str(error))
        return False

def listAllOpsItemIds(filter, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        response = ssm_client.describe_ops_items(
            OpsItemFilters=filter
        )

        opItemIds = []
        for opsItem in response['OpsItemSummaries']:
            opItemIds.append(opsItem['OpsItemId'])

        return opItemIds

    except Exception as error:
        print("Exception caught while trying to list ops item ids: " + str(error))
        return False

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

def findActiveOpsItem(parameterKey, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

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

        opsItemIds = listAllOpsItemIds(filter, region=region)

        if len(opsItemIds) != 1:
            raise Exception ("Total number of ops item(s) " + str(opsItemIds) + " found is " + len(opsItemIds) + ".  There should only exist 1.")

        return getOpsItem(opsItemIds[0])

    except Exception as error:
        print("Exception caught while trying to identify active ops item: " + str(error))
        return False

def close_window(windowId, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        ssm_client.delete_maintenance_window(
            WindowId=windowId
        )

        return True

    except Exception as error:
        print("Exception caught while trying to close maintenance window [" + windowId + "]: " + str(error))
        return False

def updateOpsItems(opsItemIds, status, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        for opsItemId in opsItemIds:
            ssm_client.update_ops_item(
                Status=status,
                OpsItemId=opsItemId
            )

        return True

    except Exception as error:
        print("Exception encountered while updating ops items: " + str(error))
        return False

def setRelatedOpsItem(opsItemId, relatedOpsItems, **kwargs):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        ssm_client.update_ops_item(
            RelatedOpsItems=relatedOpsItems,
            OpsItemId=opsItemId
        )

        return True

    except Exception as error:
        print("Exception encountered while setting related ops items: " + str(error))
        return False
    
def removeFromRelatedOpsItem(targetOpsItemId, opsItemIdToRemove):

    region = os.environ['AWS_REGION']

    if 'region' in kwargs:
        region = kwargs['region']

    session = boto3.session.Session()
    ssm_client = session.client('ssm', region)
    
    try:

        targetOpsItem = getOpsItem(targetOpsItemId)
        newRelatedList = []
        for opsItemId in targetOpsItem:
            if opsItemId['OpsItemId'] != opsItemIdToRemove:
                newRelatedList.append({'OpsItemId': opsItemId['OpsItemId']})

        ssm_client.update_ops_item(
            RelatedOpsItems=newRelatedList,
            OpsItemId=targetOpsItemId
        )

        return True

    except Exception as error:
        print("Exception encountered while removing from related ops item ids: " + str(error))
        return False
    
#Maintenance Window Functions

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
        
        return response['WindowIdentities'][0]['WindowId']
        
    except Exception as error:
        print("Exception caught while locating maintenance window [" + name + "]: " + str(error))
        return False