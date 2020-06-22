# ITSM-Controlled-Continuous-Optimization
This solution enables change management processes within popular ITSM platforms to control the optimization of infrastructure resources.  These resources include (but not limited to), CPU, Memory, Disk, Network across various on-prem, public cloud and k8s services.  

The solution available here will optimize AWS EC2 and RDS services that are managed by CloudFormation.

Requirements
- A Densify instance connected to your AWS environment that's up and running.
- ServiceNow running with the AWS service catalog connector installed.  
- EC2/RDS resources running within your AWS environment that are managed by CloudFormation

The technologies that support this solution are described below.

Parameter Repo
- Currently Supported
  - AWS Parameter Store
 
ITSM Platforms
- Currently Supported
  - ServiceNow
- Future Support
  - Jira Service Desk

Work Order Management
- Currently Supported
  - AWS Ops Center
  
IaC/Deployment Technologies
- Currently Supported
  - CloudFormation
- Future Support
  - TerraForm
  - Lambda
