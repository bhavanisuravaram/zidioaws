#!/bin/bash
# ─── Zidio Connect - EC2 Startup Script ───────────────────────────────────
# Use this as EC2 User Data OR run manually after SSH-ing into your instance

set -e

echo "=========================================="
echo "  Zidio Connect – EC2 Setup Starting..."
echo "=========================================="

# 1. Update system
sudo apt update -y && sudo apt upgrade -y

# 2. Install Python, pip, git, nginx
sudo apt install -y python3 python3-pip python3-venv git nginx

# 3. Create app directory
sudo mkdir -p /var/www/zidio-connect
sudo chown -R ubuntu:ubuntu /var/www/zidio-connect

# 4. Clone or copy your code (replace with your actual repo URL)
# git clone https://github.com/YOUR_USERNAME/zidio-connect.git /var/www/zidio-connect
# OR upload via SCP: scp -r ./zidio-connect ubuntu@YOUR_EC2_IP:/var/www/

cd /var/www/zidio-connect

# 5. Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Create environment variables file
cat > /var/www/zidio-connect/.env << 'EOF'
AWS_REGION=ap-south-1
SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:zidio-connect-notifications
SECRET_KEY=change-this-to-a-random-secret-key-123
EOF

# 7. Create systemd service for Flask/Gunicorn
sudo tee /etc/systemd/system/zidio.service > /dev/null << 'EOF'
[Unit]
Description=Zidio Connect Job Portal
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/var/www/zidio-connect
Environment="PATH=/var/www/zidio-connect/venv/bin"
EnvironmentFile=/var/www/zidio-connect/.env
ExecStart=/var/www/zidio-connect/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 8. Start and enable the service
sudo systemctl daemon-reload
sudo systemctl start zidio
sudo systemctl enable zidio

# 9. Configure Nginx as reverse proxy
sudo tee /etc/nginx/sites-available/zidio << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static/ {
        alias /var/www/zidio-connect/static/;
        expires 30d;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/zidio /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "=========================================="
echo "  ✅ Zidio Connect is LIVE!"
echo "  Visit: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "=========================================="
