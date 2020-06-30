# ITSM-Controlled-Continuous-Optimization (ICCO)
This solution deploys Densify's ICCO, designed to enable ITSM change management processes to control the optimization of infrastructure by leveraging powerful scientifically derived insights from [Densify's Optimization Engine](https://densify.com).

The highly available point source serverless architecture achieves this by extending your current ITSM change management process to enable both application owners and cloud operations to tightly control the infrastructure optimization process through insight review/approval, maintenance window scheduling and execution.

![Quick Start architecture for Densify's ITSM-Controlled-Continuous-Optimization](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/architecture.PNG)

**Insight Injection**


1) Insight Injection
  Densify delivers new insights when they are available.  
2) ITSM Collaboration
  Enables application owners to review the analysis behind any insight and decide on whether to approve for execution.  
  Enables cloud operations to schedule a maintenance window to execute the change in a pre-defined window.
3) Execution
  Executes the necessary change within the maintenance window, monitors the outcome and informs the necessary parties.
  

This solution enables change management processes within popular ITSM platforms to control the optimization of infrastructure resources.  The solution leverages Densify, a powerful optimization engine designed to analyze your infrastructure and generate insights 

These resources include (but not limited to), CPU, Memory, Disk, Network across various on-prem, public cloud and k8s services.  

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
