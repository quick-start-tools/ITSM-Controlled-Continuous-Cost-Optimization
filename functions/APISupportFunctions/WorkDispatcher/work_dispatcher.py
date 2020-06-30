import json
import boto3
import base64
import ssm_functions
import requests
import os

def lambda_handler(event, context):
    # TODO implement

	print(event)
	input = json.loads(event['body'])
	print(input)
    
	final_list = generateListOfInsights(input, event['headers'])
	for stack_id in final_list:
		dispatchJob(final_list[stack_id])
    
	return {
		'statusCode': 200,
        'body': json.dumps('New Insights Processed.')
    }

def getResourceTags(attributes, tags_to_extract):

    try:
        
        tags = {}
        for attribute in attributes:
            if attribute['id'] == "attr_resource_tags" and attribute['value'].split(" : ")[0] in tags_to_extract:
                tags[attribute['value'].split(" : ")[0]] = attribute['value'].split(" : ")[1]
                
        return tags
    
    except Exception as error:
        print("Exception caught while getting resource tags.")
        return False

def generateListOfInsights(insights, header):

    try:
    
        #get densify url and creds
        region = os.environ['AWS_REGION']
        url = ssm_functions.getParameter("/densify/config/connectionSettings/url", region)['Parameter']['Value']
        username = ssm_functions.getParameter("/densify/config/connectionSettings/username", region)['Parameter']['Value']
        password = ssm_functions.getParameter("/densify/config/connectionSettings/password", region)['Parameter']['Value']

        #get full list of attributes for all AWS systems
        headers = {"Content-Type":"application/json","Accept":"application/json"}
        response = requests.get(url + "/CIRBA/api/v2/systems/?platform=aws", auth=(username, password), headers=headers)
        response.raise_for_status()
        systems = response.json()
        
        tags = {}
        for system in systems:
            resource_tags = getResourceTags(system['attributes'], ['aws:cloudformation:stack-id', 'aws:cloudformation:logical-id', 'aws:cloudformation:stack-name'])
            if resource_tags != {}:
                new_tag_list = {}
                for tag in resource_tags:
                    new_tag_list[tag[4:]] = resource_tags[tag]
                tags[system['id']] = new_tag_list
        
        #Generate list of insights managed by CF
        insightsManagedByCF = []
        for insight in insights:
            if insight['entityId'] in tags:
                for tag in tags[insight['entityId']]:
                    insight[tag] = tags[insight['entityId']][tag]
                if 'attributes' in insight:
                    del insight['attributes']
                insightsManagedByCF.append(insight)

        #identify authorized regions
        authorizedRegions = []
        UnauthorizedRegions = []
        for insight in insightsManagedByCF:
            if insight['regionId'] not in UnauthorizedRegions:
                if insight['regionId'] not in authorizedRegions:
                    if authorizeRequest(header['Authorization'], insight['regionId']) == True:
                        authorizedRegions.append(insight['regionId'])
                    else:
                        UnauthorizedRegions.append(insight['regionId'])

        print("Authorized Regions: " + str(authorizedRegions))
        print("Unauthorized Regions: " + str(UnauthorizedRegions))
    
        #Generate final list
        final_list = {}
        for insight in insightsManagedByCF:
            if insight['regionId'] in authorizedRegions:
                current_list = []
                if insight['cloudformation:stack-id'] in final_list:
                    current_list = final_list[insight['cloudformation:stack-id']]
                insight['rptHref'] = "/systems/" + insight['entityId'] + "/analysis-report"
                current_list.append(insight)
                final_list[insight['cloudformation:stack-id']] = current_list
        
        return final_list
    
    except Exception as error:
        print("Exception caught while generating new list of insights. " + str(error))
        return False

def dispatchJob(insights):
    
    try:
        
    	lambdaEvent = insights
    	
    	client = boto3.client('lambda')
    	response = client.invoke(
    		FunctionName="ProcessNewRecommendations",
			InvocationType='Event',
			Payload=json.dumps(lambdaEvent).encode('utf-8')
		)
		
    	print(response)     
        
    except Exception as error:
        print("Exception encountered while dispatching job: " + str(error))
        return False

def authorizeRequest(authorization, region):
    
    try:
        
        authorization_type = authorization.split(" ")[0]
        
        if authorization_type != 'Basic':
            raise Exception ("Only basic authorization is supported at this time.")
        
        encoded_string = authorization.split(" ")[1]
        username = base64.b64decode(encoded_string).decode("utf-8").split(":")[0]
        password = base64.b64decode(encoded_string).decode("utf-8").split(":")[1]

        if username != ssm_functions.getParameter('/densify/config/connectionSettings/username', region)['Parameter']['Value'] or password != ssm_functions.getParameter('/densify/config/connectionSettings/password', region)['Parameter']['Value']:
            raise Exception ("Unauthorized.")
        
        return True
        
    except Exception as error:
        print("Exception caught while trying to authorize request.\n" + str(error))
        return False