"""
aws_setup.py
Run ONCE on your EC2 instance to create all three DynamoDB tables.
  python aws_setup.py

No credentials needed — EC2 IAM role handles auth automatically.
"""

import boto3

REGION = 'us-east-1'

dynamodb = boto3.client('dynamodb', region_name=REGION)

TABLES = [
    {
        'TableName': 'zidio_users',
        'KeySchema': [
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
        ],
        'BillingMode': 'PAY_PER_REQUEST',
    },
    {
        'TableName': 'zidio_jobs',
        'KeySchema': [
            {'AttributeName': 'job_id', 'KeyType': 'HASH'},
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'job_id', 'AttributeType': 'S'},
        ],
        'BillingMode': 'PAY_PER_REQUEST',
    },
    {
        'TableName': 'zidio_applications',
        'KeySchema': [
            {'AttributeName': 'application_id', 'KeyType': 'HASH'},
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'application_id', 'AttributeType': 'S'},
        ],
        'BillingMode': 'PAY_PER_REQUEST',
    },
]


def create_tables():
    existing = dynamodb.list_tables().get('TableNames', [])
    for tbl in TABLES:
        name = tbl['TableName']
        if name in existing:
            print(f'  already exists: {name}')
        else:
            dynamodb.create_table(**tbl)
            print(f'  created: {name}')

    print('\nWaiting for tables to become ACTIVE...')
    waiter = dynamodb.get_waiter('table_exists')
    for tbl in TABLES:
        waiter.wait(TableName=tbl['TableName'])
        print(f'  ACTIVE: {tbl["TableName"]}')


if __name__ == '__main__':
    print('=== Zidio Connect — DynamoDB Setup ===\n')
    create_tables()
    print('\nDone. Run: python app.py')
