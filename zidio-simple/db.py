"""
db.py — DynamoDB access layer (scan-based, no GSIs)
Credentials come from the EC2 IAM role automatically — no keys stored anywhere.
"""

import boto3
from boto3.dynamodb.conditions import Attr

REGION = 'us-east-1'

dynamodb = boto3.resource('dynamodb', region_name=REGION)

users_table        = dynamodb.Table('zidio_users')
jobs_table         = dynamodb.Table('zidio_jobs')
applications_table = dynamodb.Table('zidio_applications')


# ─── USERS ────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id):
    resp = users_table.get_item(Key={'user_id': user_id})
    return resp.get('Item')


def get_user_by_email(email):
    resp  = users_table.scan(FilterExpression=Attr('email').eq(email))
    items = resp.get('Items', [])
    return items[0] if items else None


def create_user(doc):
    users_table.put_item(Item=doc)


def update_user(user_id, updates: dict):
    expr_parts, names, values = [], {}, {}
    for k, v in updates.items():
        n = f'#f_{k}'
        val = f':v_{k}'
        expr_parts.append(f'{n} = {val}')
        names[n]  = k
        values[val] = v
    users_table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET ' + ', '.join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


# ─── JOBS ─────────────────────────────────────────────────────────────────────

def get_all_active_jobs():
    resp  = jobs_table.scan(FilterExpression=Attr('status').eq('active'))
    items = resp.get('Items', [])
    return sorted(items, key=lambda x: x.get('posted_at', ''), reverse=True)


def search_jobs(search='', location='', category=''):
    expr = Attr('status').eq('active')
    if category:
        expr = expr & Attr('category').eq(category)
    if location:
        expr = expr & Attr('location').contains(location)
    if search:
        expr = expr & (Attr('title').contains(search) | Attr('company').contains(search))
    resp  = jobs_table.scan(FilterExpression=expr)
    items = resp.get('Items', [])
    return sorted(items, key=lambda x: x.get('posted_at', ''), reverse=True)


def get_job_by_id(job_id):
    resp = jobs_table.get_item(Key={'job_id': job_id})
    return resp.get('Item')


def get_jobs_by_recruiter(recruiter_id):
    resp  = jobs_table.scan(FilterExpression=Attr('recruiter_id').eq(recruiter_id))
    items = resp.get('Items', [])
    return sorted(items, key=lambda x: x.get('posted_at', ''), reverse=True)


def create_job(doc):
    jobs_table.put_item(Item=doc)


def update_job_status(job_id, status):
    jobs_table.update_item(
        Key={'job_id': job_id},
        UpdateExpression='SET #s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': status},
    )


def delete_job(job_id):
    jobs_table.delete_item(Key={'job_id': job_id})


# ─── APPLICATIONS ─────────────────────────────────────────────────────────────

def get_application_by_id(application_id):
    resp = applications_table.get_item(Key={'application_id': application_id})
    return resp.get('Item')


def get_applications_by_job(job_id):
    resp  = applications_table.scan(FilterExpression=Attr('job_id').eq(job_id))
    items = resp.get('Items', [])
    return sorted(items, key=lambda x: x.get('applied_at', ''), reverse=True)


def get_applications_by_applicant(email):
    resp  = applications_table.scan(FilterExpression=Attr('applicant_email').eq(email))
    items = resp.get('Items', [])
    return sorted(items, key=lambda x: x.get('applied_at', ''), reverse=True)


def application_exists(job_id, applicant_email):
    resp = applications_table.scan(
        FilterExpression=Attr('job_id').eq(job_id) & Attr('applicant_email').eq(applicant_email)
    )
    return resp.get('Count', 0) > 0


def create_application(doc):
    applications_table.put_item(Item=doc)


def update_application_status(application_id, status, reviewed_at):
    applications_table.update_item(
        Key={'application_id': application_id},
        UpdateExpression='SET #s = :s, reviewed_at = :r',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': status, ':r': reviewed_at},
    )


def delete_applications_by_job(job_id):
    apps = get_applications_by_job(job_id)
    with applications_table.batch_writer() as batch:
        for app in apps:
            batch.delete_item(Key={'application_id': app['application_id']})
