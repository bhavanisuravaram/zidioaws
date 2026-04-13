"""
sns_service.py — SNS notifications
Topic ARN is fetched by name at runtime — no hardcoded ARNs anywhere.
On EC2 the IAM role gives permission to publish automatically.
"""

import boto3

REGION     = 'ap-south-1'
TOPIC_NAME = 'zidio-notifications'

_client    = None
_topic_arn = None


def _get_topic_arn():
    global _client, _topic_arn
    if _topic_arn:
        return _topic_arn
    if _client is None:
        _client = boto3.client('sns', region_name=REGION)
    # Create topic is idempotent — returns existing ARN if already exists
    resp       = _client.create_topic(Name=TOPIC_NAME)
    _topic_arn = resp['TopicArn']
    return _topic_arn


def _publish(subject: str, message: str):
    try:
        _client.publish(
            TopicArn=_get_topic_arn(),
            Subject=subject[:100],
            Message=message,
        )
    except Exception as e:
        print(f'[SNS] publish failed: {e}')


def notify_new_application(applicant_name, applicant_email, job_title, company):
    _publish(
        subject=f'New Application — {job_title} at {company}',
        message=(
            f'New application received on Zidio Connect!\n\n'
            f'Job     : {job_title}\n'
            f'Company : {company}\n'
            f'From    : {applicant_name} ({applicant_email})\n\n'
            f'Log in to your recruiter dashboard to review it.'
        ),
    )


def notify_application_status(applicant_name, job_title, company, new_status):
    emoji = '✅' if new_status == 'accepted' else '❌' if new_status == 'rejected' else '⏳'
    _publish(
        subject=f'{emoji} Application Update — {job_title}',
        message=(
            f'Hi {applicant_name},\n\n'
            f'Your application status has been updated.\n\n'
            f'Job     : {job_title}\n'
            f'Company : {company}\n'
            f'Status  : {new_status.upper()}\n\n'
            f'{"Congratulations! The recruiter will contact you soon." if new_status == "accepted" else "Thank you for applying. Keep exploring other opportunities!"}'
        ),
    )


def notify_new_job(job_title, company, location, category):
    _publish(
        subject=f'New Job — {job_title} at {company}',
        message=(
            f'A new job has been posted on Zidio Connect!\n\n'
            f'Title    : {job_title}\n'
            f'Company  : {company}\n'
            f'Location : {location}\n'
            f'Category : {category}'
        ),
    )
