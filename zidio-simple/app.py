import uuid
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (LoginManager, UserMixin,
                         login_user, logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

import db
import sns_service

app = Flask(__name__)
app.secret_key = os.urandom(24)   # fresh random key each restart — fine for EC2

# ─── FLASK-LOGIN ──────────────────────────────────────────────────────────────

login_manager = LoginManager(app)
login_manager.login_view         = 'login'
login_manager.login_message      = 'Please log in to access this page.'
login_manager.login_message_category = 'error'


class User(UserMixin):
    def __init__(self, doc):
        self.id      = doc['user_id']
        self.email   = doc['email']
        self.name    = doc['name']
        self.role    = doc['role']
        self.company = doc.get('company', '')
        self.phone   = doc.get('phone', '')
        self.skills  = doc.get('skills', '')
        self.bio     = doc.get('bio', '')

    def is_recruiter(self): return self.role == 'recruiter'
    def is_student(self):   return self.role == 'student'


@login_manager.user_loader
def load_user(user_id):
    doc = db.get_user_by_id(user_id)
    return User(doc) if doc else None


# ─── PUBLIC ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    jobs = db.get_all_active_jobs()
    return render_template('index.html', jobs=jobs)


@app.route('/jobs')
def jobs():
    search   = request.args.get('search',   '').strip()
    location = request.args.get('location', '').strip()
    category = request.args.get('category', '').strip()
    all_jobs = db.search_jobs(search=search, location=location, category=category)
    return render_template('jobs.html', jobs=all_jobs,
                           search=search, location=location, category=category)


@app.route('/job/<job_id>')
def job_detail(job_id):
    job = db.get_job_by_id(job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('jobs'))
    already_applied = False
    if current_user.is_authenticated and current_user.is_student():
        already_applied = db.application_exists(job_id, current_user.email)
    return render_template('job_detail.html', job=job, already_applied=already_applied)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'db': 'DynamoDB'})


@app.route('/api/jobs')
def api_jobs():
    return jsonify(db.get_all_active_jobs())


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        role     = request.form['role']
        company  = request.form.get('company', '').strip()

        if db.get_user_by_email(email):
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('register'))

        doc = {
            'user_id':    str(uuid.uuid4()),
            'name':       name,
            'email':      email,
            'password':   generate_password_hash(password),
            'role':       role,
            'company':    company,
            'phone':      '',
            'skills':     '',
            'bio':        '',
            'created_at': datetime.utcnow().isoformat(),
        }
        db.create_user(doc)
        login_user(User(doc))
        flash(f'Welcome to Zidio Connect, {name}!', 'success')
        return redirect(url_for('recruiter_dashboard' if role == 'recruiter' else 'student_dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        doc = db.get_user_by_email(email)
        if doc and check_password_hash(doc['password'], password):
            login_user(User(doc))
            flash(f'Welcome back, {doc["name"]}!', 'success')
            nxt = request.args.get('next')
            if nxt:
                return redirect(nxt)
            return redirect(url_for('recruiter_dashboard' if doc['role'] == 'recruiter' else 'student_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# ─── STUDENT ──────────────────────────────────────────────────────────────────

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if not current_user.is_student():
        return redirect(url_for('recruiter_dashboard'))
    apps = db.get_applications_by_applicant(current_user.email)
    return render_template('student_dashboard.html', applications=apps)


@app.route('/apply/<job_id>', methods=['GET', 'POST'])
@login_required
def apply(job_id):
    if not current_user.is_student():
        flash('Only students can apply for jobs.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))

    job = db.get_job_by_id(job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('jobs'))
    if job.get('status') != 'active':
        flash('This job is no longer accepting applications.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))
    if db.application_exists(job_id, current_user.email):
        flash('You have already applied for this job.', 'error')
        return redirect(url_for('job_detail', job_id=job_id))

    if request.method == 'POST':
        doc = {
            'application_id':  str(uuid.uuid4()),
            'job_id':          job_id,
            'job_title':       job['title'],
            'company':         job['company'],
            'recruiter_id':    job['recruiter_id'],
            'applicant_name':  current_user.name,
            'applicant_email': current_user.email,
            'applicant_id':    current_user.id,
            'phone':           request.form.get('phone', current_user.phone),
            'experience':      request.form.get('experience', ''),
            'cover_letter':    request.form.get('cover_letter', ''),
            'applied_at':      datetime.utcnow().isoformat(),
            'status':          'pending',
        }
        db.create_application(doc)
        sns_service.notify_new_application(
            applicant_name=current_user.name,
            applicant_email=current_user.email,
            job_title=job['title'],
            company=job['company'],
        )
        flash('Application submitted! We will contact you soon.', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('apply.html', job=job)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        updates = {
            'name':    request.form.get('name', current_user.name).strip(),
            'phone':   request.form.get('phone', '').strip(),
            'bio':     request.form.get('bio', '').strip(),
            'skills':  request.form.get('skills', '').strip(),
            'company': request.form.get('company', '').strip(),
        }
        new_pw = request.form.get('new_password', '').strip()
        if new_pw:
            updates['password'] = generate_password_hash(new_pw)
        db.update_user(current_user.id, updates)
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')


# ─── RECRUITER ────────────────────────────────────────────────────────────────

@app.route('/recruiter/dashboard')
@login_required
def recruiter_dashboard():
    if not current_user.is_recruiter():
        return redirect(url_for('student_dashboard'))
    my_jobs  = db.get_jobs_by_recruiter(current_user.id)
    all_apps = []
    for j in my_jobs:
        all_apps.extend(db.get_applications_by_job(j['job_id']))
    all_apps.sort(key=lambda x: x.get('applied_at', ''), reverse=True)
    stats = {
        'total_jobs':    len(my_jobs),
        'active_jobs':   sum(1 for j in my_jobs if j.get('status') == 'active'),
        'total_apps':    len(all_apps),
        'pending_apps':  sum(1 for a in all_apps if a.get('status') == 'pending'),
        'accepted_apps': sum(1 for a in all_apps if a.get('status') == 'accepted'),
    }
    return render_template('recruiter_dashboard.html',
                           jobs=my_jobs[:5], applications=all_apps[:5], stats=stats)


@app.route('/post-job', methods=['GET', 'POST'])
@login_required
def post_job():
    if not current_user.is_recruiter():
        flash('Only recruiters can post jobs.', 'error')
        return redirect(url_for('jobs'))
    if request.method == 'POST':
        doc = {
            'job_id':        str(uuid.uuid4()),
            'title':         request.form['title'],
            'company':       current_user.company or request.form.get('company', ''),
            'location':      request.form['location'],
            'category':      request.form['category'],
            'job_type':      request.form['job_type'],
            'salary':        request.form.get('salary', 'Not disclosed'),
            'description':   request.form['description'],
            'requirements':  request.form['requirements'],
            'contact_email': current_user.email,
            'recruiter_id':  current_user.id,
            'posted_at':     datetime.utcnow().isoformat(),
            'status':        'active',
        }
        db.create_job(doc)
        sns_service.notify_new_job(
            job_title=doc['title'], company=doc['company'],
            location=doc['location'], category=doc['category'],
        )
        flash('Job posted successfully!', 'success')
        return redirect(url_for('my_jobs'))
    return render_template('post_job.html')


@app.route('/my-jobs')
@login_required
def my_jobs():
    if not current_user.is_recruiter():
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    jobs_list = db.get_jobs_by_recruiter(current_user.id)
    for j in jobs_list:
        j['applicant_count'] = len(db.get_applications_by_job(j['job_id']))
    return render_template('my_jobs.html', jobs=jobs_list)


@app.route('/applicants/<job_id>')
@login_required
def applicants(job_id):
    if not current_user.is_recruiter():
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    job = db.get_job_by_id(job_id)
    if not job or job.get('recruiter_id') != current_user.id:
        flash('Job not found or access denied.', 'error')
        return redirect(url_for('my_jobs'))
    apps = db.get_applications_by_job(job_id)
    return render_template('applicants.html', job=job, applications=apps)


@app.route('/application/<application_id>/status', methods=['POST'])
@login_required
def update_application_status(application_id):
    if not current_user.is_recruiter():
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    new_status = request.form.get('status')
    if new_status not in ('accepted', 'rejected', 'pending'):
        flash('Invalid status.', 'error')
        return redirect(request.referrer or url_for('recruiter_dashboard'))

    app_doc = db.get_application_by_id(application_id)
    if not app_doc:
        flash('Application not found.', 'error')
        return redirect(request.referrer or url_for('recruiter_dashboard'))

    job = db.get_job_by_id(app_doc['job_id'])
    if not job or job.get('recruiter_id') != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('recruiter_dashboard'))

    db.update_application_status(application_id, new_status, datetime.utcnow().isoformat())
    sns_service.notify_application_status(
        applicant_name=app_doc['applicant_name'],
        job_title=app_doc['job_title'],
        company=app_doc['company'],
        new_status=new_status,
    )
    flash(f'Application marked as {new_status}.', 'success')
    return redirect(url_for('applicants', job_id=app_doc['job_id']))


@app.route('/job/<job_id>/toggle', methods=['POST'])
@login_required
def toggle_job_status(job_id):
    if not current_user.is_recruiter():
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    job = db.get_job_by_id(job_id)
    if not job or job.get('recruiter_id') != current_user.id:
        flash('Job not found or access denied.', 'error')
        return redirect(url_for('my_jobs'))
    db.update_job_status(job_id, 'closed' if job['status'] == 'active' else 'active')
    flash('Job status updated.', 'success')
    return redirect(url_for('my_jobs'))


@app.route('/job/<job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    if not current_user.is_recruiter():
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    job = db.get_job_by_id(job_id)
    if not job or job.get('recruiter_id') != current_user.id:
        flash('Job not found or access denied.', 'error')
        return redirect(url_for('my_jobs'))
    db.delete_applications_by_job(job_id)
    db.delete_job(job_id)
    flash('Job deleted.', 'success')
    return redirect(url_for('my_jobs'))


# ─── SEED ─────────────────────────────────────────────────────────────────────

def seed():
    if db.get_all_active_jobs():
        print('Already seeded.')
        return

    rid = str(uuid.uuid4())
    db.create_user({
        'user_id': rid, 'name': 'Demo Recruiter',
        'email': 'recruiter@zidio.in',
        'password': generate_password_hash('password123'),
        'role': 'recruiter', 'company': 'Zidio Digital',
        'phone': '', 'skills': '', 'bio': '',
        'created_at': datetime.utcnow().isoformat(),
    })
    db.create_user({
        'user_id': str(uuid.uuid4()), 'name': 'Demo Student',
        'email': 'student@zidio.in',
        'password': generate_password_hash('password123'),
        'role': 'student', 'company': '',
        'phone': '9999999999', 'skills': 'Python, React',
        'bio': 'Final year CS student.',
        'created_at': datetime.utcnow().isoformat(),
    })

    jobs = [
        ('Python Backend Developer', 'TechSoft Solutions', 'Hyderabad', 'Technology', 'Full-time', '8-12 LPA', 'Build REST APIs using Flask and AWS.', '3+ years Python, Flask, AWS.'),
        ('UI/UX Designer', 'Zidio Digital', 'Bangalore', 'Design', 'Full-time', '6-10 LPA', 'Design interfaces for web and mobile.', 'Figma, Adobe XD, 2+ years.'),
        ('AWS Cloud Engineer', 'CloudBase India', 'Hyderabad', 'Technology', 'Full-time', '12-18 LPA', 'Manage AWS infrastructure.', 'AWS certification, 3+ years cloud.'),
        ('Digital Marketing Executive', 'GrowthHive', 'Remote', 'Marketing', 'Remote', '4-6 LPA', 'Drive SEO, SEM, social campaigns.', 'Google Ads, Meta Ads, 1-2 years.'),
        ('React Frontend Intern', 'StartupNest', 'Pune', 'Technology', 'Internship', '15000/month', 'Build React components.', 'React basics, HTML/CSS/JS.'),
        ('Finance Analyst', 'FinEdge Corp', 'Mumbai', 'Finance', 'Full-time', '7-10 LPA', 'Analyze financial data.', 'CA/MBA Finance, Excel, Power BI.'),
    ]
    for title, company, loc, cat, jtype, sal, desc, req in jobs:
        db.create_job({
            'job_id': str(uuid.uuid4()),
            'title': title, 'company': company, 'location': loc,
            'category': cat, 'job_type': jtype, 'salary': sal,
            'description': desc, 'requirements': req,
            'contact_email': 'recruiter@zidio.in',
            'recruiter_id': rid,
            'posted_at': datetime.utcnow().isoformat(),
            'status': 'active',
        })
    print('Seeded 6 jobs + demo users.')
    print('  student@zidio.in   / password123')
    print('  recruiter@zidio.in / password123')


if __name__ == '__main__':
    seed()
    app.run(host='0.0.0.0', port=5000, debug=False)
