# ITSM-Controlled-Continuous-Optimization (ICCO)
This solution deploys Densify's ICCO, designed to enable ITSM change management processes to control the optimization of infrastructure by leveraging powerful scientifically derived insights from [Densify's Optimization Engine](https://densify.com).

The highly available point source serverless architecture achieves this by extending your current ITSM change management process to enable both application owners and cloud operations to tightly control the infrastructure optimization process through insight review/approval, maintenance window scheduling and execution.

## Architecture Overview

![Quick Start architecture for Densify's ITSM-Controlled-Continuous-Optimization](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/architecture.PNG)

## Primary Sequences

**Insight Injection**
Densify periodically analyzes your infrastructure resource utilization to generate insights to optimize supply allocations.  The specific insight is dependant on the service being optimized.  e.g For EC2, the optimization parameter is *InstanceType*.  For RDS, the optimization parameter is *DBInstanceClass*.  For ASGs, the optimization parameter is *InstanceType, minSize, maxSize*.

A webhook is used to trigger the delivery of the insights to API-gateway upon insight availability.  These insights are pushed and stored within parameter store.  As parameter store is a regional technology, the specific insight is delivered to the region in which the insight's infrastructure service exists.

![Insight Injection](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/InsightInjection.PNG)

**ITSM Change Ticket Creation**
Cloudwatch events monitor parameter store for new insights or changes to an existing insights state.  When triggered, the CW event will invoke a series of functions to create a change ticket within the configured ITSM platfrom.

![ITSM Ticket Creation](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/CreateITSMTicket.PNG)

**Approval Aquisition**
Application owners can review the complete scientific analysis behind the insight through the ITSM console.  Th owner can choose to approve or deny the execution of this insight.  If approved, the complete lifecycle of the executed can be viewed from the change ticket.

![Approval Acquisition](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/ApproveInsight.PNG)

**Window Acquisition**
All changes are executed inside an approved maintenance window, which is scheduled by cloud operations.  To help faciliate the acquisition of a window a work order is created in AWS Ops Center.  This is routed to a cloud ops resource, who can now review the order and schedule an appropriate window.  

![Window Acquisition](https://github.com/densify-quick-start/ITSM-Controlled-Continuous-Optimization/blob/master/img/AcquireMW.PNG)

**Execution**
On the arrival of the maintenance window, a series of functions trigger and mointor the update process through CloudFormation.  The enhanced CloudFormation templates enable the IaC technology to dynamically reference approved insights directly from the parameter repo.

## Prerequisites

In the current release, this solution will work with the following technologies.
- ITSM Platform: *ServiceNow*
- Optimization Engine: *Densify*
- Parameter Repo: *AWS Parameter Store*
- IaC Technology: *AWS CloudFormation*

1) A Densify instance needs to be online and configured to audit and analyze your AWS account.  If you do not already have one, please request a [trial instance](https://www.densify.com/product/trial).

2) A ServiceNow instance has to be available and ready to take on new change requests.  If you do not have one, you can get a free [PDI instance](https://developer.servicenow.com/dev.do) from ServiceNow.

3) The [AWS ITSM connector](https://docs.aws.amazon.com/servicecatalog/latest/adminguide/integrations-servicenow.html) installed on your ServiceNow instance.  

4) An AWS account that has some provisioned EC2, RDS and/or ASG services provisioned and managed through AWS CloudFormation.

## Other

For architectural details, best practices, step-by-step instructions, and customization options, see the deployment guide.  To post feedback, submit feature ideas, or report bugs, use the Issues section of this GitHub repo.
