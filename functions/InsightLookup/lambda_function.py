'''
DensifyCloudFormationProvider

Creator: Dinesh Raveendran
Version: 1.0
'''

import boto3
import json
import sys
import datetime
import cfnresponse
from cfn_flip import flip, to_yaml, to_json
import orchestrator

def handler(event, context):

	print("Execution Starting.")
	print(event)
	
	if event['RequestType'] == 'Delete':
		send_response(event, context, cfnresponse.SUCCESS, 'Successfully Deleted.', {})
	else:
		recommendations = {}
		defaultSettings = event['ResourceProperties']
		accountId = defaultSettings['ServiceToken'].split(":")[4]
		region = defaultSettings['ServiceToken'].split(":")[3]
		stackName = event['StackId'].split(":")[5].split("/")[1]
		try:
			resources = identify_resources(stackName, region)
			recommendations = orchestrator.get_recommendations(resources, accountId, region, identifyAdapter())
		except Exception as e:
			send_response(event, context, cfnresponse.FAILED, str(e), {})
		else:
			print("Recommendations before backfilled defaults: " + str(recommendations))
			recommendations = backfill_defaults(recommendations, defaultSettings)
			print("Final list of recommendations: " + str(recommendations))
			send_response(event, context, cfnresponse.SUCCESS, 'Sucessfully extracted recommendations.', recommendations)

	return {
		'statusCode': 200,
		'body': json.dumps('Execution Complete.')
	}
	
def identifyAdapter():
	
	ssm_client = boto3.client('ssm')
	
	response = ssm_client.get_parameter(
		Name='/densify/config/resourceProviderAdapter',
		WithDecryption=True
	)
	
	adapter = response['Parameter']['Value']
	
	if (adapter == 'Direct Reference'):
		client = boto3.client('ssm')
		client.put_parameter(
			Name='/densify/config/lastUpdatedTimestamp',
			Description='Densify Last Update.',
			Value=str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")),
			Type='String',
			Overwrite=True,
			Tier='Standard'
		)
	
	return adapter

def is_json(template):
	converted_template = json.loads(json.dumps(template))
	try:
		json.loads(converted_template)
	except TypeError as e:
		return True
	except Exception as e:
		return False
		
def identify_resources(stackName, region):
	#this function will build out the list of resources for analysis
	
	client = boto3.client('cloudformation', region)
	response = client.list_stack_resources(
		StackName=stackName,
	)
	
	return_obj = {}
	ec2_resources = {}
	rds_resources = {}
	asg_resources = {}

	#Generate list for existing resources
	resources = response['StackResourceSummaries']
	for resource in resources:
		if resource['ResourceType'] == 'AWS::EC2::Instance':
			ec2_resources[resource['LogicalResourceId']]=resource['PhysicalResourceId']
		elif resource['ResourceType'] == 'AWS::RDS::DBInstance':
			rds_resources[resource['LogicalResourceId']]=resource['PhysicalResourceId']
		elif resource['ResourceType'] == 'AWS::AutoScaling::AutoScalingGroup':
			asg_resources[resource['LogicalResourceId']]=resource['PhysicalResourceId']

	response = client.get_template(
	    StackName=stackName
	)
	
	#Identify resources that don't currently exist	
	if is_json(response['TemplateBody']):
		resources_fullList = json.loads(json.dumps(response['TemplateBody']))['Resources']
	else:
		resources_fullList = json.loads(flip(response['TemplateBody']))['Resources']
		
	print(resources_fullList)
	for resource in resources_fullList:
		if resources_fullList[resource]['Type'] == 'AWS::EC2::Instance':
			if resource not in ec2_resources:
				ec2_resources[resource]="DoesNotExist"
		if resources_fullList[resource]['Type'] == 'AWS::RDS::DBInstance':
			if resource not in rds_resources:
				rds_resources[resource]="DoesNotExist"
		if resources_fullList[resource]['Type'] == 'AWS::AutoScaling::AutoScalingGroup':
			if resource not in asg_resources:
				asg_resources[resource]="DoesNotExist"
	
	#Build and return final object
	return_obj['ec2']=ec2_resources
	return_obj['rds']=rds_resources
	return_obj['asg']=asg_resources
	print("Identified Resources: EC2[" + str(len(ec2_resources)) + "] RDS[" + str(len(rds_resources)) + "] ASG[" + str(len(asg_resources)) + "] --> " + str(return_obj))
	
	return return_obj

# This function will backfill all of the default settings provided by the customer for resources that currently
# do not exist or have no recommendation in Densify
def backfill_defaults(recommendations, defaultSettings):
	
	for serviceType in recommendations:
		for logicalResourceName in recommendations[serviceType]:
			for parameter in recommendations[serviceType][logicalResourceName]:
				key = logicalResourceName + "." + parameter
				if recommendations[serviceType][logicalResourceName][parameter] == "DoesNotExist" and key in defaultSettings:
					recommendations[serviceType][logicalResourceName][parameter] = defaultSettings[logicalResourceName + "." + parameter]

	return recommendations

# This function will send the response back to the custom resource
def send_response(event, context, response_status, response_message, recommendations):
	responseBody = {}
	responseBody['LogStreamName'] = context.log_stream_name
	responseBody['Status'] = response_status
	responseBody['Message'] = response_message
			
	if response_status is cfnresponse.SUCCESS and event['RequestType'] != 'Delete':
		ec2_recommendations = recommendations['ec2']
		for logicalName in ec2_recommendations:
			responseBody[logicalName + ".InstanceType"] = ec2_recommendations[logicalName]['InstanceType']

		rds_recommendations = recommendations['rds']
		for logicalName in rds_recommendations:
			responseBody[logicalName + ".DBInstanceClass"] = rds_recommendations[logicalName]['DBInstanceClass']
			
		asg_recommendations = recommendations['asg']
		for logicalName in asg_recommendations:
			responseBody[logicalName + ".InstanceType"] = asg_recommendations[logicalName]['InstanceType']
			responseBody[logicalName + ".MinSize"] = asg_recommendations[logicalName]['MinSize']
			responseBody[logicalName + ".MaxSize"] = asg_recommendations[logicalName]['MaxSize']
		
	cfnresponse.send(event, context, response_status, responseBody)