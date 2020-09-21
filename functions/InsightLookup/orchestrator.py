import boto3
import json
import ParameterStoreAdapter
import DensifyAdapter

def get_recommendations(resources, accountId, region, adapter):
	
	print("Extracting densify credentials from parameter store.")
	ssm_client = boto3.client('ssm', region)
	try:
		densifyUrl = ssm_client.get_parameter(Name='/densify/config/connectionSettings/url', WithDecryption=True)['Parameter']['Value']
		densifyUser = ssm_client.get_parameter(Name='/densify/config/connectionSettings/username', WithDecryption=True)['Parameter']['Value']
		densifyPass = ssm_client.get_parameter(Name='/densify/config/connectionSettings/password', WithDecryption=True)['Parameter']['Value']
	except Exception as error:
		raise Exception(str(error))
	
	print("Extracting recommendations through adapter[" + adapter + "]")
	recommendations = {}

	#Generate EC2 Recommendations
	ec2_recommendations = {}
	ec2_resources = resources['ec2']
	for LogicalResourceId in ec2_resources:
		ec2_recommendations[LogicalResourceId] = get_ec2_recommendation(ec2_resources[LogicalResourceId], accountId, region, adapter, densifyUrl, densifyUser, densifyPass)

	recommendations['ec2'] = ec2_recommendations

	#Generate RDS Recommendations
	rds_recommendations = {}
	rds_resources = resources['rds']
	for LogicalResourceId in rds_resources:
		rds_recommendations[LogicalResourceId] = get_rds_recommendation(rds_resources[LogicalResourceId], accountId, region, adapter, densifyUrl, densifyUser, densifyPass)

	recommendations['rds'] = rds_recommendations

	#Generate ASG Recommendations
	asg_recommendations = {}
	asg_resources = resources['asg']
	for LogicalResourceId in asg_resources:
		asg_recommendations[LogicalResourceId] = get_asg_recommendation(asg_resources[LogicalResourceId], accountId, region, adapter, densifyUrl, densifyUser, densifyPass)

	recommendations['asg'] = asg_recommendations

	return recommendations

def get_ec2_recommendation(id, accountId, region, adapter, densifyUrl, densifyUser, densifyPass):
    
	ec2_recommendation = {}
	ec2_client = boto3.client('ec2', region)
	
	response = {}
	try:
		response = ec2_client.describe_instances(
			InstanceIds=[
				id,
			]
		)
	except Exception as e:
		print(e)
		ec2_recommendation['InstanceType'] = "DoesNotExist"
		return ec2_recommendation
		
	try:
		
		if adapter == 'Parameter Store':
			ec2_recommendation = ParameterStoreAdapter.get_ec2_recommendation(id, region)
		elif adapter == 'Direct Reference':
			ec2_recommendation = DensifyAdapter.get_ec2_recommendation(id, accountId, region, densifyUrl, densifyUser, densifyPass)
		else:
			raise Exception("Adapter[" + adapter + "] does not exist.")

	except Exception as error:
		print(error)
		ec2_recommendation['InstanceType'] = response['Reservations'][0]['Instances'][0]['InstanceType']

	return ec2_recommendation
	
def get_rds_recommendation(id, accountId, region, adapter, densifyUrl, densifyUser, densifyPass):
    
	rds_recommendation = {}
	rds_client = boto3.client('rds', region)

	response = {}
	try:
		response = rds_client.describe_db_instances(
			DBInstanceIdentifier=id
		)
	except Exception as e:
		print(e)
		rds_recommendation['DBInstanceClass'] = "DoesNotExist"
		return rds_recommendation

	try:
		
		if adapter == 'Parameter Store':
			rds_recommendation = ParameterStoreAdapter.get_rds_recommendation(id, region)
		elif adapter == 'Direct Reference':
			rds_recommendation = DensifyAdapter.get_rds_recommendation(id, accountId, region, densifyUrl, densifyUser, densifyPass)
		else:
			raise Exception("Adapter[" + adapter + "] does not exist.")

	except Exception as error:
		print(error)
		rds_recommendation['DBInstanceClass'] = response['DBInstances'][0]['DBInstanceClass']

	return rds_recommendation

def get_asg_recommendation(id, accountId, region, adapter, densifyUrl, densifyUser, densifyPass):
    
	asg_recommendation = {}
	asg_client = boto3.client('autoscaling', region)

	response = {}
	try:
		response_asg = asg_client.describe_auto_scaling_groups(
			AutoScalingGroupNames=[
				id,
			]
		)
		response_lc = asg_client.describe_launch_configurations(
			LaunchConfigurationNames=[
				response_asg['AutoScalingGroups'][0]['LaunchConfigurationName'],
			]
		)
	except Exception as e:
		print(e)
		asg_recommendation['InstanceType'] = "DoesNotExist"
		asg_recommendation['MinSize'] = "DoesNotExist"
		asg_recommendation['MaxSize'] = "DoesNotExist"
		return asg_recommendation

	try:
		
		if adapter == 'Parameter Store':
			asg_recommendation = ParameterStoreAdapter.get_asg_recommendation(id, region)
		elif adapter == 'Direct Reference':
			asg_recommendation = DensifyAdapter.get_asg_recommendation(id, accountId, region, densifyUrl, densifyUser, densifyPass)
		else:
			raise Exception("Adapter[" + adapter + "] does not exist.")

	except Exception as error:
		print(error)
		asg_recommendation['InstanceType'] = response_lc['LaunchConfigurations'][0]['InstanceType']
		asg_recommendation['MinSize'] = response_asg['AutoScalingGroups'][0]['MinSize']
		asg_recommendation['MaxSize'] = response_asg['AutoScalingGroups'][0]['MaxSize']

	return asg_recommendation