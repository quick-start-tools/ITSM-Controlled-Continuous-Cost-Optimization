import json
import boto3

def get_asg_recommendation(id, region):
    
	asg_recommendation = {}
	ssm_client = boto3.client('ssm', region)

	parameter_key_instanceType = '/densify/iaas/asg/' + id + '/instanceType'
	parameter_key_minSize = '/densify/iaas/asg/' + id + '/minSize'
	parameter_key_maxSize = '/densify/iaas/asg/' + id + '/maxSize'
	
	try:
		
		response = ssm_client.get_parameter(
			Name=parameter_key_instanceType,
			WithDecryption=True
		)
		
		asg_recommendation['InstanceType'] = response['Parameter']['Value']
		
		response = ssm_client.get_parameter(
			Name=parameter_key_minSize,
			WithDecryption=True
		)
		
		asg_recommendation['MinSize'] = response['Parameter']['Value']
		
		response = ssm_client.get_parameter(
			Name=parameter_key_maxSize,
			WithDecryption=True
		)
		
		asg_recommendation['MaxSize'] = response['Parameter']['Value']

	except ssm_client.exceptions.ParameterNotFound as error:
		raise Exception("ASG recommendation does not exist in parameter store.")

	return asg_recommendation  
    
def get_rds_recommendation(id, region):
    
	rds_recommendation = {}
	ssm_client = boto3.client('ssm', region)

	parameter_key = '/densify/iaas/rds/' + id + '/dbInstanceClass'

	try:
		
		response = ssm_client.get_parameter(
			Name=parameter_key,
			WithDecryption=True
		)
		
		rds_recommendation['DBInstanceClass'] = response['Parameter']['Value']

	except ssm_client.exceptions.ParameterNotFound as error:
		raise Exception("RDS recommendation does not exist in parameter store.")

	return rds_recommendation
    
def get_ec2_recommendation(id, region):
    
	ec2_recommendation = {}
	ssm_client = boto3.client('ssm', region)

	parameter_key = '/densify/iaas/ec2/' + id + '/instanceType'
	
	try:
		
		response = ssm_client.get_parameter(
			Name=parameter_key,
			WithDecryption=True
		)
		
		ec2_recommendation['InstanceType'] = response['Parameter']['Value']

	except ssm_client.exceptions.ParameterNotFound as error:
		raise Exception("EC2 recommendation does not exist in parameter store.")

	return ec2_recommendation