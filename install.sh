#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print colored messages
print_message() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Function to check command success
check_command() {
    if [ $? -ne 0 ]; then
        print_error "$1 failed"
        exit 1
    fi
}

# Update system packages
print_message "Updating system packages..."
apt-get update && apt-get upgrade -y
check_command "System update"

# Install required packages
print_message "Installing required packages..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common
check_command "Package installation"

# Install Docker
print_message "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
check_command "Docker installation"

# Start and enable Docker
systemctl start docker
systemctl enable docker
check_command "Docker service setup"

# Install Docker Compose
print_message "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
check_command "Docker Compose installation"

# Install Certbot
print_message "Installing Certbot..."
apt-get install -y certbot
check_command "Certbot installation"

# Create directory for Conduwuit
mkdir -p /opt/conduwuit
cd /opt/conduwuit

# Get domain name
read -p "Enter your domain name (e.g., conduwuit.example.com): " DOMAIN_NAME
while [ -z "$DOMAIN_NAME" ]; do
    print_error "Domain name cannot be empty"
    read -p "Enter your domain name (e.g., conduwuit.example.com): " DOMAIN_NAME
done

# Get email for Let's Encrypt
read -p "Enter your email address for Let's Encrypt: " EMAIL_ADDRESS
while [ -z "$EMAIL_ADDRESS" ]; do
    print_error "Email address cannot be empty"
    read -p "Enter your email address for Let's Encrypt: " EMAIL_ADDRESS
done

# Get Conduwuit admin credentials
read -p "Enter desired admin username: " ADMIN_USERNAME
while [ -z "$ADMIN_USERNAME" ]; do
    print_error "Admin username cannot be empty"
    read -p "Enter desired admin username: " ADMIN_USERNAME
done

read -s -p "Enter admin password: " ADMIN_PASSWORD
echo
while [ -z "$ADMIN_PASSWORD" ]; do
    print_error "Admin password cannot be empty"
    read -s -p "Enter admin password: " ADMIN_PASSWORD
    echo
done

# Generate random secret key
SECRET_KEY=$(openssl rand -hex 32)

# Generate TURN secret
TURN_SECRET=$(openssl rand -hex 32)

# Create coturn.conf
print_message "Creating Coturn configuration..."
cat > /opt/conduwuit/coturn.conf << EOL
use-auth-secret
static-auth-secret=${TURN_SECRET}
realm=${DOMAIN_NAME}
# Security
no-tcp
no-tls
no-dtls
# Ports
min-port=49152
max-port=49252
# Logging
verbose
# Other
stale-nonce=0
EOL

# Create docker-compose.yml
print_message "Creating Docker Compose configuration..."
cat > docker-compose.yml << EOL
version: '3'

services:
  conduwuit:
    image: ghcr.io/girlbossceo/conduwuit:latest
    restart: always
    ports:
      - "80:8000"
      - "443:8443"
    volumes:
      - ./data:/data
      - ./certs:/certs
    environment:
      - CONDUWUIT_SERVER_NAME=${DOMAIN_NAME}
      - CONDUWUIT_REPORT_STATS=false
      - CONDUWUIT_DATABASE_PATH=/data/conduwuit.db
      - CONDUWUIT_SIGNING_KEY=${SECRET_KEY}
      - CONDUWUIT_ENABLE_REGISTRATION=false
      - CONDUWUIT_TURN_URI=turn:${DOMAIN_NAME}:3478
      - CONDUWUIT_TURN_SECRET=${TURN_SECRET}
      - CONDUWUIT_TURN_TTL=86400

  coturn:
    image: coturn/coturn:latest
    restart: always
    network_mode: host
    volumes:
      - ./coturn.conf:/etc/coturn/turnserver.conf:ro
    depends_on:
      - conduwuit
EOL

# Get SSL certificate
print_message "Obtaining SSL certificate..."
certbot certonly --standalone -d ${DOMAIN_NAME} --email ${EMAIL_ADDRESS} --agree-tos -n
check_command "SSL certificate generation"

# Copy SSL certificates
mkdir -p /opt/conduwuit/certs
cp /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem /opt/conduwuit/certs/
cp /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem /opt/conduwuit/certs/
chmod -R 755 /opt/conduwuit/certs

# Start Conduwuit
print_message "Starting Conduwuit..."
docker-compose up -d
check_command "Conduwuit startup"

# Create admin user
print_message "Creating admin user..."
docker-compose exec -T conduwuit register_new_matrix_user \
    -c /data/conduwuit.yaml \
    -u ${ADMIN_USERNAME} \
    -p ${ADMIN_PASSWORD} \
    -a
check_command "Admin user creation"

# Setup complete
print_message "Installation complete!"
echo
print_message "Your Conduwuit instance is now running at https://${DOMAIN_NAME}"
echo
print_message "TURN server is configured at turn:${DOMAIN_NAME}:3478"
print_message "TURN secret: ${TURN_SECRET}"
echo
print_message "Admin credentials:"
echo "Username: ${ADMIN_USERNAME}"
echo "Password: [HIDDEN]"
echo
print_warning "Please save these credentials in a secure location!"
echo
print_message "To view logs, run: docker-compose logs -f"
print_message "To stop the server, run: docker-compose down"
print_message "To start the server, run: docker-compose up -d" 