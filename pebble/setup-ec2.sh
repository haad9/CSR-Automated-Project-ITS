#!/bin/bash
# ============================================================
# CSR Demo EC2 Setup Script
# Run this via SSM or on first boot to configure Pebble CA + Nginx
# ============================================================
set -euo pipefail

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Starting CSR EC2 setup on $INSTANCE_ID ($PUBLIC_IP)"

# ── Docker ────────────────────────────────────────────────────────────────
log "Installing Docker..."
yum update -y
amazon-linux-extras install docker -y
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# ── Nginx ─────────────────────────────────────────────────────────────────
log "Installing Nginx..."
amazon-linux-extras install nginx1 -y
mkdir -p /etc/nginx/certs
mkdir -p /etc/nginx/conf.d

cat > /etc/nginx/nginx.conf << 'NGINX_EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events { worker_connections 1024; }

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile on;
    keepalive_timeout 65;

    server {
        listen 80 default_server;
        server_name _;
        location /health { return 200 'OK'; add_header Content-Type text/plain; }
        return 301 https://$host$request_uri;
    }

    include /etc/nginx/conf.d/*.conf;
}
NGINX_EOF

systemctl start nginx
systemctl enable nginx

# ── Pebble CA ─────────────────────────────────────────────────────────────
log "Setting up Pebble CA..."
mkdir -p /opt/pebble/config

cat > /opt/pebble/docker-compose.yml << 'PEBBLE_EOF'
version: '3.8'
services:
  pebble:
    image: letsencrypt/pebble:latest
    container_name: pebble-ca
    restart: unless-stopped
    ports:
      - "14000:14000"
      - "15000:15000"
    environment:
      - PEBBLE_VA_NOSLEEP=1
      - PEBBLE_VA_ALWAYS_VALID=1
      - PEBBLE_WFE_NONCEREJECT=0
    command: pebble -config /test/config/pebble-config.json -strict=false
    volumes:
      - /opt/pebble/config:/test/config
PEBBLE_EOF

cat > /opt/pebble/config/pebble-config.json << 'CONFIG_EOF'
{
  "pebble": {
    "listenAddress": "0.0.0.0:14000",
    "managementListenAddress": "0.0.0.0:15000",
    "certificate": "test/certs/localhost/cert.pem",
    "privateKey": "test/certs/localhost/key.pem",
    "httpPort": 5002,
    "tlsPort": 5001,
    "ocspResponderURL": "",
    "externalAccountBindingRequired": false
  }
}
CONFIG_EOF

cd /opt/pebble
docker-compose up -d

# ── SSM Parameters ────────────────────────────────────────────────────────
log "Registering SSM parameters..."

aws ssm put-parameter \
  --name "/csr/ec2-instance-id" \
  --value "$INSTANCE_ID" \
  --type "String" \
  --overwrite \
  --region "$REGION"

aws ssm put-parameter \
  --name "/csr/ec2-public-ip" \
  --value "$PUBLIC_IP" \
  --type "String" \
  --overwrite \
  --region "$REGION"

aws ssm put-parameter \
  --name "/csr/pebble-url" \
  --value "https://$PUBLIC_IP:14000" \
  --type "String" \
  --overwrite \
  --region "$REGION"

# ── Health check ──────────────────────────────────────────────────────────
log "Running health checks..."
sleep 5

# Check Nginx
if curl -sf http://localhost/health > /dev/null; then
  log "Nginx: OK"
else
  log "Nginx: WARNING - health check failed"
fi

# Check Pebble
if curl -sf --insecure https://localhost:14000/dir > /dev/null; then
  log "Pebble CA: OK"
else
  log "Pebble CA: WARNING - not ready yet (may need 10-15s)"
fi

log "EC2 setup complete!"
log "  Instance: $INSTANCE_ID"
log "  Public IP: $PUBLIC_IP"
log "  Pebble CA: https://$PUBLIC_IP:14000"
log "  Nginx: http://$PUBLIC_IP"
