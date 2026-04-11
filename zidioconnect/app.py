from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zidio-connect-secret-2024')

# ─── AWS CONFIG ─────────────────────────────────────────────────────────────
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')  # Mumbai region for India

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)

JOBS_TABLE = 'zidio-jobs'
APPLICATIONS_TABLE = 'zidio-applications'
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')

# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    jobs = get_all_jobs()
    return render_template('index.html', jobs=jobs)

@app.route('/jobs')
def jobs():
    search = request.args.get('search', '')
    location = request.args.get('location', '')
    category = request.args.get('category', '')
    all_jobs = get_all_jobs()

    if search:
        all_jobs = [j for j in all_jobs if search.lower() in j.get('title','').lower()
                    or search.lower() in j.get('company','').lower()]
    if location:
        all_jobs = [j for j in all_jobs if location.lower() in j.get('location','').lower()]
    if category:
        all_jobs = [j for j in all_jobs if category == j.get('category','')]

    return render_template('jobs.html', jobs=all_jobs, search=search,
                           location=location, category=category)

@app.route('/job/<job_id>')
def job_detail(job_id):
    job = get_job_by_id(job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('jobs'))
    return render_template('job_detail.html', job=job)

@app.route('/post-job', methods=['GET', 'POST'])
def post_job():
    if request.method == 'POST':
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'title': request.form['title'],
            'company': request.form['company'],
            'location': request.form['location'],
            'category': request.form['category'],
            'job_type': request.form['job_type'],
            'salary': request.form.get('salary', 'Not disclosed'),
            'description': request.form['description'],
            'requirements': request.form['requirements'],
            'contact_email': request.form['contact_email'],
            'posted_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
        save_job(job)
        notify_new_job(job)
        flash('Job posted successfully!', 'success')
        return redirect(url_for('job_detail', job_id=job_id))
    return render_template('post_job.html')

@app.route('/apply/<job_id>', methods=['GET', 'POST'])
def apply(job_id):
    job = get_job_by_id(job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('jobs'))

    if request.method == 'POST':
        app_id = str(uuid.uuid4())
        application = {
            'application_id': app_id,
            'job_id': job_id,
            'job_title': job['title'],
            'company': job['company'],
            'applicant_name': request.form['name'],
            'applicant_email': request.form['email'],
            'phone': request.form.get('phone', ''),
            'experience': request.form.get('experience', ''),
            'cover_letter': request.form.get('cover_letter', ''),
            'applied_at': datetime.utcnow().isoformat(),
            'status': 'pending'
        }
        save_application(application)
        notify_application(application, job)
        flash('Application submitted successfully! We will contact you soon.', 'success')
        return redirect(url_for('job_detail', job_id=job_id))

    return render_template('apply.html', job=job)

@app.route('/dashboard')
def dashboard():
    jobs = get_all_jobs()
    applications = get_all_applications()
    stats = {
        'total_jobs': len(jobs),
        'total_applications': len(applications),
        'active_jobs': len([j for j in jobs if j.get('status') == 'active']),
        'pending_apps': len([a for a in applications if a.get('status') == 'pending'])
    }
    return render_template('dashboard.html', jobs=jobs[:5],
                           applications=applications[:5], stats=stats)

# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/api/jobs', methods=['GET'])
def api_jobs():
    return jsonify(get_all_jobs())

@app.route('/api/jobs/<job_id>', methods=['GET'])
def api_job(job_id):
    job = get_job_by_id(job_id)
    return jsonify(job) if job else (jsonify({'error': 'Not found'}), 404)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Zidio Connect'})

# ─── DYNAMODB HELPERS ────────────────────────────────────────────────────────

def get_all_jobs():
    try:
        table = dynamodb.Table(JOBS_TABLE)
        response = table.scan()
        jobs = response.get('Items', [])
        return sorted(jobs, key=lambda x: x.get('posted_at', ''), reverse=True)
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return []

def get_job_by_id(job_id):
    try:
        table = dynamodb.Table(JOBS_TABLE)
        response = table.get_item(Key={'job_id': job_id})
        return response.get('Item')
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return None

def save_job(job):
    try:
        table = dynamodb.Table(JOBS_TABLE)
        table.put_item(Item=job)
    except ClientError as e:
        print(f"DynamoDB error: {e}")

def save_application(application):
    try:
        table = dynamodb.Table(APPLICATIONS_TABLE)
        table.put_item(Item=application)
    except ClientError as e:
        print(f"DynamoDB error: {e}")

def get_all_applications():
    try:
        table = dynamodb.Table(APPLICATIONS_TABLE)
        response = table.scan()
        apps = response.get('Items', [])
        return sorted(apps, key=lambda x: x.get('applied_at', ''), reverse=True)
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return []

# ─── SNS NOTIFICATIONS ───────────────────────────────────────────────────────

def notify_new_job(job):
    if not SNS_TOPIC_ARN:
        return
    try:
        message = f"""
🆕 New Job Posted on Zidio Connect!

Title:    {job['title']}
Company:  {job['company']}
Location: {job['location']}
Type:     {job['job_type']}
Category: {job['category']}

Visit Zidio Connect to apply now!
        """
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=f"New Job: {job['title']} at {job['company']}"
        )
    except ClientError as e:
        print(f"SNS error: {e}")

def notify_application(application, job):
    if not SNS_TOPIC_ARN:
        return
    try:
        message = f"""
📩 New Application Received!

Job:       {job['title']} at {job['company']}
Applicant: {application['applicant_name']}
Email:     {application['applicant_email']}
Phone:     {application.get('phone', 'N/A')}
Applied:   {application['applied_at']}

Login to Zidio Connect dashboard to review.
        """
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=f"New Application: {application['applicant_name']} for {job['title']}"
        )
    except ClientError as e:
        print(f"SNS error: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
