import json
import boto3
from botocore.vendored import requests

def getRecommendation(densifyUrl, username, password, id, accountId, region, searchParams):
	
	header = {'content-type': 'application/json', 'accept': 'application/json'}
	try:
		analysisList = requests.get(densifyUrl + '/CIRBA/api/v2/analysis/cloud', headers=header, auth=(username, password))
		for analysis in analysisList.json():
			r = requests.get(densifyUrl + '/CIRBA/api/v2' + analysis['analysisResults'] + searchParams, headers=header, auth=(username, password))
			if (len(r.json()) == 1):
				return r.json()[0]
		return {}
	except Exception as error:
		raise Exception(str(error))
		
def get_asg_recommendation(id, accountId, region, densifyUrl, username, password):
    
	asg_recommendation = {}

	try:

		searchParams = '?name=' + id + '&accountIdRef=' + accountId + '&region=' + region + '&implementationMethod=Self Optimization'
		
		recommendation = getRecommendation(densifyUrl, username, password, id, accountId, region, searchParams)
		if len(recommendation) != 0:
			if recommendation['approvalType'] != 'na':
				asg_recommendation['InstanceType'] = recommendation['recommendedType']
				asg_recommendation['MinSize'] = recommendation['minGroupRecommended']
				asg_recommendation['MaxSize'] = recommendation['maxGroupRecommended']
			else:
				asg_recommendation['InstanceType'] = recommendation['currentType']
				asg_recommendation['MinSize'] = recommendation['minGroupCurrent']
				asg_recommendation['MaxSize'] = recommendation['maxGroupCurrent']
		else:
			raise Exception("ASG Recommendation not found in Densify.")
	
	except Exception as error:
		raise Exception(str(error))

	return asg_recommendation  
    
def get_rds_recommendation(id, accountId, region, densifyUrl, username, password):
    
	rds_recommendation = {}

	try:

		searchParams = '?name=' + id + '&accountIdRef=' + accountId + '&region=' + region + '&implementationMethod=Self Optimization'
		recommendation = getRecommendation(densifyUrl, username, password, id, accountId, region, searchParams)

		if len(recommendation) != 0:
			if recommendation['approvalType'] != 'na':
				rds_recommendation['DBInstanceClass'] = recommendation['recommendedType']
			else:
				rds_recommendation['DBInstanceClass'] = recommendation['currentType']
		else:
			raise Exception("RDS Recommendation not found in Densify.")
	
	except Exception as error:
		raise Exception(str(error))

	return rds_recommendation
    
def get_ec2_recommendation(id, accountId, region, densifyUrl, username, password):
    
	ec2_recommendation = {}

	try:

		searchParams = '?resourceId=' + id + '&accountIdRef=' + accountId + '&region=' + region + '&implementationMethod=Self Optimization'
		recommendation = getRecommendation(densifyUrl, username, password, id, accountId, region, searchParams)

		if len(recommendation) != 0:
			if recommendation['approvalType'] != 'na':
				ec2_recommendation['InstanceType'] = recommendation['recommendedType']
			else:
				ec2_recommendation['InstanceType'] = recommendation['currentType']
		else:
			raise Exception("EC2 Recommendation not found in Densify.")
	
	except Exception as error:
		raise Exception(str(error))

	return ec2_recommendation