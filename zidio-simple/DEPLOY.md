# Zidio Connect — AWS Deployment
## EC2 + DynamoDB + SNS + IAM Role

---

## Step 1 — Create IAM Role

1. **IAM → Roles → Create Role**
2. Trusted entity → **AWS Service → EC2**
3. **Create inline policy** → paste `iam_policy.json`
4. Name the role: `ZidioEC2Role`
5. Save

---

## Step 2 — Launch EC2

- AMI: **Ubuntu 22.04 LTS**
- Type: **t2.micro** (free tier)
- IAM Role: attach **ZidioEC2Role**
- Security Group inbound rules:

| Port | Source    | Purpose        |
|------|-----------|----------------|
| 22   | Your IP   | SSH            |
| 5000 | 0.0.0.0/0 | Flask app      |

---

## Step 3 — SSH & Setup

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

sudo apt update && sudo apt install -y python3-pip python3-venv

# Upload project from local machine:
# scp -i your-key.pem -r zidio-simple/ ubuntu@YOUR_EC2_IP:~/zidio
```

---

## Step 4 — Install & Run

```bash
cd ~/zidio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create DynamoDB tables (run once)
python aws_setup.py

# Start the app
python app.py
```

Visit: `http://YOUR_EC2_IP:5000`

---

## Step 5 — SNS Email Alerts (optional)

The app auto-creates the SNS topic `zidio-notifications` on first SNS call.

To receive email alerts:
1. **SNS → Topics → zidio-notifications → Create subscription**
2. Protocol: **Email**
3. Endpoint: your email address
4. Confirm from inbox

---

## Step 6 — Keep Running (Gunicorn + systemd)

```bash
sudo nano /etc/systemd/system/zidio.service
```

```ini
[Unit]
Description=Zidio Connect
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/zidio
Environment="PATH=/home/ubuntu/zidio/venv/bin"
ExecStart=/home/ubuntu/zidio/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable zidio
sudo systemctl start zidio
sudo systemctl status zidio
```

---

## How IAM Role Works (no credentials on disk)

```
EC2 Instance
  └── IAM Role: ZidioEC2Role attached
        └── boto3 auto-fetches temp credentials from
            http://169.254.169.254/latest/meta-data/
        └── No AWS keys stored anywhere in code or .env
```

## Demo Accounts

| Email | Password | Role |
|-------|----------|------|
| student@zidio.in | password123 | Student |
| recruiter@zidio.in | password123 | Recruiter |
