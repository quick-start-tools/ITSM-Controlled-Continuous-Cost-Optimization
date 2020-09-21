# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 14:34:54 2020

@author: draveendran
"""


import requests
import json
import os
import ssm_functions
from requests.adapters import HTTPAdapter

serviceNowURL, serviceNowUser, serviceNowPass, densifyURL, densifyUser, densifyPass = "","","","","",""

def executeFunction(function, **kwargs):
    
    try:
        
        print(function + " request received with input " + str(kwargs))
        
        global serviceNowURL, serviceNowUser, serviceNowPass, densifyURL, densifyUser, densifyPass
        
        serviceNowURL = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/url')['Parameter']['Value']
        serviceNowUser = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/username')['Parameter']['Value']
        serviceNowPass = ssm_functions.getParameter('/densify/config/serviceNow/connectionSettings/password')['Parameter']['Value']
        densifyURL = ssm_functions.getParameter('/densify/config/connectionSettings/url')['Parameter']['Value']
        densifyUser = ssm_functions.getParameter('/densify/config/connectionSettings/username')['Parameter']['Value']
        densifyPass = ssm_functions.getParameter('/densify/config/connectionSettings/password')['Parameter']['Value']
        
        if function == 'open':
            resp = createTicket(kwargs['recommendation'])
        elif function == 'update':
            resp = updateTicket(kwargs['ticketId'], kwargs['input'])
        elif function == 'schedule':
            resp = updateTicket(kwargs['ticketId'], kwargs['input'])
        elif function == 'close':
            resp = updateTicket(kwargs['ticketId'], kwargs['input'])
        elif function == 'cancel':
            resp = updateTicket(kwargs['ticketId'], kwargs['input'])
        else:
            print("This function [" + function + "] isn't recognized.")
            return False
        
        return resp
        
    except Exception as error:
        print("Exception encountered while execution " + function + ".  " + str(error))
        return False

def invokeRestAPI(type, apiEndPoint, username, password, headers, data):

    try:
    
        s = requests.Session()
        s.mount(apiEndPoint, HTTPAdapter(max_retries=int(os.environ['retryAttempts'])))
        cookies = {'laravel_session': 'oRrEZq0oadEJMaTpx7aXEPBDXdJOFyQGjySZVjE0'}
        
        if type == 'post':
            response = s.post(apiEndPoint, auth=(username, password), headers=headers, data=data, timeout=None, cookies=cookies)
        elif type == 'put':
            response = s.put(apiEndPoint, auth=(username, password), headers=headers, data=data, timeout=None, cookies=cookies)     

        return response
    
    except Exception as error:
        print("Exception encountered when invoking REST API: " + str(error))
        return False
      
def updateTicket(ticketId, nameValuePairs):

    try:
        
        print("Updating ticket with the following name-pairs.")
        print(nameValuePairs)
        
        apiEndPoint = serviceNowURL + '/api/now/table/change_request/' + ticketId
        headers = {"Content-Type":"application/json","Accept":"application/json"}
        
        response = invokeRestAPI("put", apiEndPoint, serviceNowUser, serviceNowPass, headers, json.dumps(nameValuePairs))
        #response = requests.put(apiEndPoint, auth=(serviceNowUser, serviceNowPass), headers=headers, data=json.dumps(nameValuePairs))
        
        if response == False:
            raise Exception ("Failed to invoke API.")
        
        if response.status_code != 200: 
            raise Exception ('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)
            
        #print(response.content)
        return {'status': 'success'}
            
    except Exception as error:
        print("Exception encountered while updating ticket.")
        print(error)
        return False

def createTicket(recommendation):
    
    try:

        print("Creating ticket with the following recommendation.")
        print(recommendation)

        lookup ={"High": "1", "Medium": "2", "Low": "3"}
        apiEndPoint = serviceNowURL + '/api/now/table/change_request'
        data =  {"impact" : lookup['Low'],
                 "urgency": lookup['Low'],
                 "category": "None",
                 "assignment_group": "None",
                 "short_description": "Densify Optimization Insight for " + recommendation['name'],
                 "description": json.dumps(recommendation)}
        
        headers = {"Content-Type":"application/json","Accept":"application/json"}
        
        response = invokeRestAPI("post", apiEndPoint, serviceNowUser, serviceNowPass, headers, json.dumps(data))
        #response = requests.post(apiEndPoint, auth=(serviceNowUser, serviceNowPass), headers=headers ,data=json.dumps(data))

        if response == False:
            raise Exception ("API Invocation failure.")
            
        if response.status_code != 201:
            print("Status Code: " + str(response.status_code))
            print("Headers: " + str(response.headers))
            print("Content: " + str(response.content))
            raise Exception ('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)

        jsonresp = json.loads(response.text)
        ticketId = jsonresp['result']['sys_id']
        
        print("Attach IA Report: " + str(os.environ['attachImpactAnalysisReport']))
        if str(os.environ['attachImpactAnalysisReport']) == "False" or (downloadImpactAnalysisReport(recommendation) and attachFileToTicket(ticketId, '/tmp/ImpactAnalysisReport.pdf')):
            return {'status': 'success', 'ticketId': ticketId}
        else:
            raise Exception("Failed to download or attach impact analysis report.")
            
    except Exception as error:
        print("Error encountered during ticket creation.")
        print(error)
        return False

def attachFileToTicket(ticketId, filename):

    try:
    
        print("Attaching impact analysis report to ITSM ticket.")
        
        contentType = {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'doc': 'application/msword', 'jpg': 'image/jpeg', 'png': 'image/png', 'xlsx': 'application/xlsx', 'xls': 'application/vnd.ms-excel', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'pdf': 'application/pdf'}

        if len(filename.split('.')) != 2 and filename.split('.')[1] not in contentType:
            raise Exception("This file type cannot be attached to the ticket.")
            
        headers = {"Content-Type": contentType[filename.split('.')[1]], "Accept":"application/json"}
        apiEndPoint = serviceNowURL + "/api/now/attachment/file?table_name=change_request&table_sys_id=" + ticketId + "&file_name=" + filename.split("/")[2]
        data = open(filename, 'rb').read()
        
        response = invokeRestAPI("post", apiEndPoint, serviceNowUser, serviceNowPass, headers, data)
        #response = requests.post(apiEndPoint, auth=(serviceNowUser, serviceNowPass), headers=headers, data=data)
        
        if response == False:
            raise Exception ("API Invocation failure.")
        
        if response.status_code != 201:
            raise Exception ('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)
            
        #print(json.loads(response.text))
        return True
        
    except Exception as error:
        print("Exception encountered while attaching the file [" + filename + "] to ticket [" + ticketId + "].")
        print(error)
        return False

def downloadImpactAnalysisReport(recommendation):

    try:
    
        print("Downloading impact analysis report from Densify.")

        apiEndPoint = densifyURL + "/CIRBA/api/v2" + recommendation['rptHref']
        response = requests.get(apiEndPoint, auth=(densifyUser, densifyPass))
        
        if response.status_code != 200:
            raise Exception ('Status:', response.status_code, 'Headers:', response.headers, 'Error Response:', response.content)

        #print(json.loads(response.text))
        open('/tmp/ImpactAnalysisReport.pdf', 'wb').write(response.content)
                
        return True

    except Exception as error:
        print("Exception encountered while downloading the impact analysis report.")
        print(error)
        return False