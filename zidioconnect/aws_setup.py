#!/usr/bin/env python3
"""
Zidio Connect - AWS Setup Script
Run this ONCE to create DynamoDB tables and SNS topic
Usage: python3 aws_setup.py
"""

import boto3
import json
from botocore.exceptions import ClientError

REGION = 'ap-south-1'  # Mumbai – closest for India

dynamodb = boto3.client('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)

def create_jobs_table():
    print("Creating zidio-jobs table...")
    try:
        dynamodb.create_table(
            TableName='zidio-jobs',
            KeySchema=[{'AttributeName': 'job_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'job_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ zidio-jobs table created")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("ℹ️  zidio-jobs table already exists")
        else:
            raise

def create_applications_table():
    print("Creating zidio-applications table...")
    try:
        dynamodb.create_table(
            TableName='zidio-applications',
            KeySchema=[{'AttributeName': 'application_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'application_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ zidio-applications table created")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("ℹ️  zidio-applications table already exists")
        else:
            raise

def create_sns_topic():
    print("Creating SNS topic...")
    response = sns.create_topic(Name='zidio-connect-notifications')
    topic_arn = response['TopicArn']
    print(f"✅ SNS Topic ARN: {topic_arn}")
    return topic_arn

def subscribe_email_to_sns(topic_arn, email):
    print(f"Subscribing {email} to SNS topic...")
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol='email',
        Endpoint=email
    )
    print(f"✅ Check {email} inbox to confirm subscription!")

def create_iam_policy():
    print("Creating IAM policy for EC2 access...")
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:*:table/zidio-jobs",
                    f"arn:aws:dynamodb:{REGION}:*:table/zidio-applications"
                ]
            },
            {
                "Effect": "Allow",
                "Action": ["sns:Publish"],
                "Resource": "*"
            }
        ]
    }
    try:
        response = iam.create_policy(
            PolicyName='ZidioConnectPolicy',
            PolicyDocument=json.dumps(policy_document),
            Description='Policy for Zidio Connect EC2 to access DynamoDB and SNS'
        )
        print(f"✅ IAM Policy ARN: {response['Policy']['Arn']}")
        return response['Policy']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print("ℹ️  IAM Policy already exists")
        else:
            raise

def create_ec2_role():
    print("Creating IAM Role for EC2...")
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        response = iam.create_role(
            RoleName='ZidioConnectEC2Role',
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='EC2 role for Zidio Connect'
        )
        print(f"✅ IAM Role: ZidioConnectEC2Role")
        return response['Role']['RoleName']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print("ℹ️  IAM Role already exists")
        else:
            raise

if __name__ == '__main__':
    print("=" * 50)
    print("  Zidio Connect – AWS Setup")
    print("=" * 50)

    create_jobs_table()
    create_applications_table()
    topic_arn = create_sns_topic()

    email = input("\nEnter your email for job/application notifications: ").strip()
    if email:
        subscribe_email_to_sns(topic_arn, email)

    create_iam_policy()
    create_ec2_role()

    print("\n" + "=" * 50)
    print("✅ AWS Setup Complete!")
    print(f"\n📌 Add this to your EC2 environment:")
    print(f"   export SNS_TOPIC_ARN={topic_arn}")
    print(f"   export AWS_REGION={REGION}")
    print("=" * 50)
