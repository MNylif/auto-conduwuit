#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_debug() {
    echo -e "${BLUE}[*]${NC} $1"
}

# Function to check command success
check_command() {
    if [ $? -ne 0 ]; then
        print_error "$1 failed"
        print_debug "Last few lines of docker logs:"
        docker-compose logs --tail=20 2>/dev/null || true
        exit 1
    fi
}

# Check if ports are available
check_ports() {
    print_debug "Checking if required ports are available..."
    
    for port in 80 443 3478 49152:49252; do
        if netstat -tuln | grep -q ":$port "; then
            print_error "Port $port is already in use. Please free this port before continuing."
            exit 1
        fi
    done
}

# Check system requirements
print_debug "Checking system requirements..."
if ! command -v apt-get &> /dev/null; then
    print_error "This script requires a Debian/Ubuntu-based system."
    exit 1
fi

# Stop any running Docker containers
print_debug "Stopping any existing Docker containers..."
docker-compose down 2>/dev/null || true

# Check if ports are available
check_ports

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
    software-properties-common \
    net-tools
check_command "Package installation"

# Install Docker with progress
print_message "Installing Docker..."
print_debug "Downloading Docker install script..."
curl -fsSL https://get.docker.com -o get-docker.sh
print_debug "Running Docker install script..."
sh get-docker.sh
check_command "Docker installation"

# Start and enable Docker
print_debug "Starting Docker service..."
systemctl start docker
print_debug "Enabling Docker service..."
systemctl enable docker
check_command "Docker service setup"

# Verify Docker is running
print_debug "Verifying Docker service..."
if ! systemctl is-active --quiet docker; then
    print_error "Docker service is not running"
    exit 1
fi

# Install Docker Compose
print_message "Installing Docker Compose..."
print_debug "Downloading Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
check_command "Docker Compose installation"

# Install Certbot
print_message "Installing Certbot..."
apt-get install -y certbot
check_command "Certbot installation"

# Create directory for Conduwuit
print_debug "Creating Conduwuit directory..."
mkdir -p /opt/conduwuit
cd /opt/conduwuit || exit 1

# Get domain name
read -p "Enter your domain name (e.g., conduwuit.example.com): " DOMAIN_NAME
while [ -z "$DOMAIN_NAME" ]; do
    print_error "Domain name cannot be empty"
    read -p "Enter your domain name (e.g., conduwuit.example.com): " DOMAIN_NAME
done

# Verify domain resolves
print_debug "Verifying domain DNS..."
if ! host "$DOMAIN_NAME" > /dev/null 2>&1; then
    print_warning "Unable to resolve domain $DOMAIN_NAME. Please ensure DNS is properly configured."
    read -p "Continue anyway? (y/N): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

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

# Start Conduwuit with proper waiting
print_message "Starting Conduwuit..."
docker-compose pull
check_command "Docker image pull"

print_debug "Starting containers..."
docker-compose up -d
check_command "Container startup"

# Wait for services to be ready
print_debug "Waiting for services to be ready..."
sleep 10

# Check if containers are running
print_debug "Verifying container status..."
if ! docker-compose ps | grep -q "Up"; then
    print_error "Containers failed to start properly"
    print_debug "Container logs:"
    docker-compose logs
    exit 1
fi

# Create admin user with retry
print_message "Creating admin user..."
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker-compose exec -T conduwuit register_new_matrix_user \
        -c /data/conduwuit.yaml \
        -u "${ADMIN_USERNAME}" \
        -p "${ADMIN_PASSWORD}" \
        -a; then
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            print_warning "Failed to create admin user, retrying in 5 seconds..."
            sleep 5
        else
            print_error "Failed to create admin user after $MAX_RETRIES attempts"
            print_debug "Container logs:"
            docker-compose logs conduwuit
            exit 1
        fi
    fi
done

# Verify services are accessible
print_debug "Verifying services are accessible..."
if ! curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN_NAME}" | grep -q "200\|301\|302"; then
    print_warning "Unable to access Conduwuit web interface. Please check your firewall settings."
fi

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
print_message "Management commands:"
print_message "- View logs: docker-compose logs -f"
print_message "- Stop server: docker-compose down"
print_message "- Start server: docker-compose up -d"
print_message "- Restart server: docker-compose restart"
echo
print_debug "If you experience any issues, please check the logs using: docker-compose logs" 