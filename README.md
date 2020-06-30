# ITSM-Controlled-Continuous-Optimization (ICCO)
This solution deploys Densify's ICCO, designed to enable ITSM change management processes to control the optimization of infrastructure by leveraging powerful scientifically derived insights from [Densify's Optimization Engine](https://densify.com).

The highly available point source serverless architecture achieves this by extending your current ITSM change management process to enable both application owners and cloud operations to tightly control the infrastructure optimization process through insight review/approval, maintenance window scheduling and execution.

![Quick Start architecture for Densify's ITSM-Controlled-Continuous-Optimization](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/architecture.PNG)

**Insight Injection**
Densify periodically analyzes your infrastructure resource utilization to generate insights to optimize supply allocations.  The specific insight is dependant on the service being optimized.  e.g For EC2, the optimization parameter is InstanceType.  For RDS, the optimization parameter is DBInstanceClass.  For ASGs, the optimization parameter is InstanceType, minSize, maxSize.

A webhook is used to trigger the delivery of the insights to API-gateway upon insight availability.  These insights are pushed and stored within parameter store.  As parameter store is a regional technology, the specific insight is delivered to the region in which the insight's infrastructure service exists.

**ITSM Change Ticket Creation**
Cloudwatch events monitor parameter store for new insights or changes to an existing insights state.  When triggered, the CW event will invoke a series of functions to create a change ticket within the configured ITSM platfrom.

**Approval Aquisition**
Application owners can review the complete scientific analysis behind the insight through the ITSM console.  Th owner can choose to approve or deny the execution of this insight.  If approved, the complete lifecycle of the executed can be viewed from the change ticket.

**Window Acquisition**
All changes are executed inside an approved maintenance window, which is scheduled by cloud operations.  To help faciliate the acquisition of a window a work order is created in AWS Ops Center.  This is routed to a cloud ops resource, who can now review the order and schedule an appropriate window.  

**Execution**
On the arrival of the maintenance window, a series of functions trigger and mointor the update process through CloudFormation.  The enhanced CloudFormation templates enable the IaC technology to dynamically reference approved insights directly from the parameter repo.

1) Insight Injection
  Densify delivers new insights when they are available.  
2) ITSM Collaboration
  Enables application owners to review the analysis behind any insight and decide on whether to approve for execution.  
  Enables cloud operations to schedule a maintenance window to execute the change in a pre-defined window.
3) Execution
  Executes the necessary change within the maintenance window, monitors the outcome and informs the necessary parties.
  
In the current release, this solution will work with the following technologies.
- ITSM Platform: *ServiceNow*
- Optimization Engine: *Densify*
- Parameter Repo: *AWS Parameter Store*
- IaC Technology: *AWS CloudFormation*


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
