# Zidio Connect – Complete AWS Deployment Guide

## Project Structure
```
zidio-connect/
├── app.py                  # Flask backend (main app)
├── requirements.txt        # Python dependencies
├── aws_setup.py            # One-time AWS resource creation
├── ec2_setup.sh            # EC2 server configuration script
├── templates/
│   ├── base.html           # Layout with navbar & footer
│   ├── index.html          # Homepage with hero + job listings
│   ├── jobs.html           # Browse jobs with filters
│   ├── job_detail.html     # Single job view
│   ├── post_job.html       # Employer job posting form
│   ├── apply.html          # Candidate application form
│   └── dashboard.html      # Admin dashboard with stats
└── static/
    └── style.css           # Complete CSS styling
```

---

## STEP 1 – AWS Account & IAM Setup

### 1.1 Create IAM User (for local development)
1. Go to **AWS Console → IAM → Users → Create User**
2. Username: `zidio-dev`
3. Attach policies:
   - `AmazonDynamoDBFullAccess`
   - `AmazonSNSFullAccess`
   - `AmazonEC2FullAccess`
4. Create **Access Key** → Download CSV

### 1.2 Configure AWS CLI locally
```bash
pip install awscli
aws configure
# Enter: Access Key ID, Secret Key, Region: ap-south-1, Format: json
```

---

## STEP 2 – Create AWS Resources

### 2.1 Run the setup script
```bash
python3 aws_setup.py
```
This automatically creates:
- ✅ `zidio-jobs` DynamoDB table
- ✅ `zidio-applications` DynamoDB table
- ✅ `zidio-connect-notifications` SNS topic
- ✅ `ZidioConnectPolicy` IAM policy
- ✅ `ZidioConnectEC2Role` IAM role

### 2.2 Confirm SNS Email
- Check your inbox for AWS confirmation email
- Click **"Confirm subscription"**

---

## STEP 3 – Create EC2 Instance

### 3.1 Launch EC2
1. Go to **AWS Console → EC2 → Launch Instance**
2. Settings:
   - **Name**: `zidio-connect-server`
   - **AMI**: Ubuntu Server 22.04 LTS (Free tier eligible)
   - **Instance type**: `t2.micro` (Free tier) or `t3.small` for production
   - **Key pair**: Create new → `zidio-key` → Download `.pem` file

### 3.2 Security Group Rules
| Type | Protocol | Port | Source |
|------|----------|------|--------|
| SSH | TCP | 22 | Your IP |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |
| Custom | TCP | 5000 | 0.0.0.0/0 |

### 3.3 Attach IAM Role to EC2
1. Select instance → **Actions → Security → Modify IAM Role**
2. Select `ZidioConnectEC2Role`
3. Click **Update IAM Role**

> ⚠️ This gives EC2 permission to access DynamoDB and SNS WITHOUT storing credentials on the server.

---

## STEP 4 – Deploy Application to EC2

### 4.1 Connect to EC2
```bash
chmod 400 zidio-key.pem
ssh -i zidio-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### 4.2 Upload your code
```bash
# From your LOCAL machine (new terminal):
scp -i zidio-key.pem -r ./zidio-connect ubuntu@YOUR_EC2_IP:/home/ubuntu/
```

### 4.3 On EC2 – Install and run
```bash
# Move files to web directory
sudo mv /home/ubuntu/zidio-connect /var/www/zidio-connect
sudo chown -R ubuntu:ubuntu /var/www/zidio-connect
cd /var/www/zidio-connect

# Install Python and dependencies
sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv nginx
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
echo "AWS_REGION=ap-south-1" >> .env
echo "SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:zidio-connect-notifications" >> .env
echo "SECRET_KEY=your-random-secret-key-here" >> .env
```

### 4.4 Run with Gunicorn (production server)
```bash
# Test first:
gunicorn --bind 0.0.0.0:5000 app:app

# If it works, set up as a service (run the full ec2_setup.sh):
chmod +x ec2_setup.sh
./ec2_setup.sh
```

---

## STEP 5 – Configure Nginx (Reverse Proxy)

Nginx sits in front of Gunicorn to handle web traffic:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /var/www/zidio-connect/static/;
        expires 30d;
    }
}
```

```bash
sudo systemctl restart nginx
sudo systemctl status nginx  # Check it's running
```

---

## STEP 6 – Verify Everything Works

```bash
# Check app service
sudo systemctl status zidio

# Check logs if there are errors
sudo journalctl -u zidio -f

# Test the app
curl http://localhost:5000/health
# Should return: {"service": "Zidio Connect", "status": "healthy"}
```

Visit: `http://YOUR_EC2_PUBLIC_IP` in your browser ✅

---

## STEP 7 – (Optional) Add Domain + HTTPS

### 7.1 Point domain to EC2
- Go to your domain registrar → Add **A Record** pointing to EC2 public IP

### 7.2 Install SSL with Let's Encrypt (Free)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## AWS Architecture Summary

```
Internet
    │
    ▼
[Route 53 / Domain]  ──optional──►  [EC2 Instance]
                                          │
                                    [Nginx :80/:443]
                                          │
                                    [Gunicorn :5000]
                                          │
                                    [Flask App]
                                        /   \
                                       /     \
                              [DynamoDB]   [SNS]
                            zidio-jobs    Notifications
                            zidio-apps    (Email alerts)
                                 │
                              [IAM Role]
                            (No hardcoded
                             credentials)
```

---

## Common Commands (Cheat Sheet)

```bash
# Restart app after code changes
sudo systemctl restart zidio

# View live logs
sudo journalctl -u zidio -f

# Check nginx
sudo systemctl status nginx

# SSH into EC2
ssh -i zidio-key.pem ubuntu@YOUR_EC2_IP

# Upload updated files
scp -i zidio-key.pem -r ./zidio-connect ubuntu@YOUR_EC2_IP:/home/ubuntu/

# Test DynamoDB connection
python3 -c "import boto3; t=boto3.resource('dynamodb',region_name='ap-south-1').Table('zidio-jobs'); print(t.scan())"
```

---

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `ap-south-1` |
| `SNS_TOPIC_ARN` | SNS topic for notifications | `arn:aws:sns:...` |
| `SECRET_KEY` | Flask session secret | Random string |

---

## Free Tier Limits (Monthly)

| Service | Free Tier |
|---------|-----------|
| EC2 t2.micro | 750 hours/month |
| DynamoDB | 25 GB storage, 25 RCU/WCU |
| SNS | 1 million notifications |
| Data Transfer | 15 GB/month |

> 💡 This entire setup runs FREE on AWS Free Tier for 12 months!
