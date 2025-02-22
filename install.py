#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import socket
import random
import string
import shutil
from pathlib import Path
import urllib.request
import getpass
from typing import Tuple, Optional
import socket

# ANSI colors
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_message(message: str) -> None:
    print(f"{Colors.GREEN}[+]{Colors.NC} {message}")

def print_warning(message: str) -> None:
    print(f"{Colors.YELLOW}[!]{Colors.NC} {message}")

def print_error(message: str) -> None:
    print(f"{Colors.RED}[-]{Colors.NC} {message}")
    
def print_debug(message: str) -> None:
    print(f"{Colors.BLUE}[*]{Colors.NC} {message}")

def run_command(command: str, shell: bool = False, env: dict = None) -> Tuple[int, str, str]:
    """Run a command and return returncode, stdout, stderr"""
    try:
        # Set DEBIAN_FRONTEND to noninteractive for apt commands
        custom_env = os.environ.copy()
        if env:
            custom_env.update(env)
        if 'apt-get' in command:
            custom_env['DEBIAN_FRONTEND'] = 'noninteractive'
        
        process = subprocess.Popen(
            command if shell else command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            env=custom_env
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()
    except Exception as e:
        return 1, "", str(e)

def check_root() -> None:
    """Check if script is run as root"""
    if os.geteuid() != 0:
        print_error("Please run as root (use sudo)")
        sys.exit(1)

def check_system() -> None:
    """Check system requirements"""
    print_debug("Checking system requirements...")
    
    # Check if system is Debian/Ubuntu
    if not os.path.exists('/etc/debian_version'):
        print_error("This script requires a Debian/Ubuntu-based system")
        sys.exit(1)

def check_ports() -> None:
    """Check if required ports are available"""
    print_debug("Checking if required ports are available...")
    ports = [80, 443, 3478] + list(range(49152, 49252))
    
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print_error(f"Port {port} is already in use")
            sys.exit(1)

def install_packages() -> None:
    """Install required packages"""
    print_message("Installing required packages...")
    
    # First, remove any existing certbot PPA to avoid errors
    print_debug("Removing any existing certbot repositories...")
    run_command("rm -f /etc/apt/sources.list.d/certbot-*", shell=True)
    
    # Update package list
    print_debug("Updating package lists...")
    cmd = "apt-get update"
    returncode, stdout, stderr = run_command(cmd)
    if returncode != 0:
        print_warning(f"Package list update warning (non-fatal): {stderr}")

    # Install basic packages
    packages = [
        'apt-transport-https',
        'ca-certificates',
        'curl',
        'gnupg',
        'lsb-release',
        'software-properties-common',
        'net-tools',
        'snapd',
        'curl'  # Ensure curl is installed for healthcheck
    ]
    
    print_debug("Installing basic packages...")
    cmd = f"DEBIAN_FRONTEND=noninteractive apt-get install -y {' '.join(packages)}"
    returncode, stdout, stderr = run_command(cmd, shell=True)
    if returncode != 0:
        print_error(f"Failed to install packages: {stderr}")
        sys.exit(1)

    # Ensure snapd is running
    print_debug("Ensuring snapd service is running...")
    run_command("systemctl start snapd")
    run_command("systemctl enable snapd")
    
    # Wait for snap to be ready
    print_debug("Waiting for snap service to be ready...")
    time.sleep(5)
    
    # Install certbot via snap
    print_debug("Installing Certbot via snap...")
    
    # Remove any existing certbot
    print_debug("Removing any existing certbot installations...")
    run_command("apt-get remove -y certbot", shell=True)
    run_command("apt-get autoremove -y", shell=True)
    run_command("rm -f /usr/bin/certbot")
    
    # Install certbot using snap
    print_debug("Installing Certbot...")
    max_retries = 3
    for i in range(max_retries):
        returncode, stdout, stderr = run_command("snap install --classic certbot")
        if returncode == 0:
            break
        if i < max_retries - 1:
            print_warning(f"Failed to install Certbot (attempt {i+1}/{max_retries}). Retrying...")
            time.sleep(5)
        else:
            print_error("Failed to install Certbot via snap")
            print_error("Please try installing certbot manually:")
            print_error("sudo snap install --classic certbot")
            print_error("sudo ln -s /snap/bin/certbot /usr/bin/certbot")
            sys.exit(1)
    
    # Create symlink
    print_debug("Creating Certbot symlink...")
    run_command("ln -sf /snap/bin/certbot /usr/bin/certbot")
    
    # Final verification
    print_debug("Verifying Certbot installation...")
    returncode, stdout, stderr = run_command("which certbot")
    if returncode != 0:
        print_error("Failed to verify certbot installation")
        sys.exit(1)
    
    print_debug("Certbot installation verified successfully")

def install_docker() -> None:
    """Install Docker"""
    print_message("Installing Docker...")
    
    # Download Docker install script
    print_debug("Downloading Docker install script...")
    urllib.request.urlretrieve("https://get.docker.com", "get-docker.sh")
    
    # Install Docker
    print_debug("Installing Docker...")
    returncode, stdout, stderr = run_command("sh get-docker.sh")
    if returncode != 0:
        print_error(f"Docker installation failed: {stderr}")
        sys.exit(1)
    
    # Start Docker service
    print_debug("Starting Docker service...")
    run_command("systemctl start docker")
    run_command("systemctl enable docker")
    
    # Verify Docker is running
    returncode, stdout, stderr = run_command("systemctl is-active docker")
    if returncode != 0:
        print_error("Docker service is not running")
        sys.exit(1)

def install_docker_compose() -> None:
    """Install Docker Compose"""
    print_message("Installing Docker Compose...")
    
    # Get latest version
    url = "https://github.com/docker/compose/releases/latest/download/docker-compose-Linux-x86_64"
    target = "/usr/local/bin/docker-compose"
    
    print_debug("Downloading Docker Compose...")
    urllib.request.urlretrieve(url, target)
    os.chmod(target, 0o755)

def get_user_input() -> Tuple[str, str, str, str]:
    """Get user input for configuration"""
    # Get domain name
    while True:
        domain = input("Enter your domain name (e.g., conduwuit.example.com): ").strip()
        if domain:
            break
        print_error("Domain name cannot be empty")
    
    # Get TURN domain
    while True:
        turn_domain = input(f"Enter your TURN server domain (default: turn.{domain}): ").strip()
        if not turn_domain:
            turn_domain = f"turn.{domain}"
        break
    
    # Verify domains resolve
    print_debug("Verifying domain DNS...")
    try:
        socket.gethostbyname(domain)
        socket.gethostbyname(turn_domain)
    except socket.gaierror:
        print_warning(f"Unable to resolve domain {domain} or {turn_domain}")
        if input("Continue anyway? (y/N): ").lower() != 'y':
            sys.exit(1)
    
    # Get email
    while True:
        email = input("Enter your email address for Let's Encrypt: ").strip()
        if email:
            break
        print_error("Email address cannot be empty")
    
    # Get admin credentials
    while True:
        admin_user = input("Enter desired admin username: ").strip()
        if admin_user:
            break
        print_error("Admin username cannot be empty")
    
    while True:
        admin_pass = getpass.getpass("Enter admin password: ").strip()
        if admin_pass:
            break
        print_error("Admin password cannot be empty")
    
    return domain, turn_domain, email, admin_user, admin_pass

def get_ssl_certificate(domain: str, email: str) -> None:
    """Get SSL certificate from Let's Encrypt"""
    print_message("Obtaining SSL certificate...")
    
    # Stop any services using port 80
    print_debug("Stopping any services using port 80...")
    services_to_stop = ['apache2', 'nginx', 'httpd']
    for service in services_to_stop:
        run_command(f"systemctl stop {service}", shell=True)
    
    # Verify port 80 is available
    print_debug("Verifying port 80 is available...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 80))
    sock.close()
    if result == 0:
        print_error("Port 80 is still in use. Please free it before continuing.")
        sys.exit(1)
    
    # Try to get SSL certificate
    max_retries = 3
    for i in range(max_retries):
        print_debug(f"Attempting to obtain SSL certificate (attempt {i+1}/{max_retries})...")
        
        # Verify certbot is available
        returncode, stdout, stderr = run_command("which certbot")
        if returncode != 0:
            print_error("Certbot not found. Please ensure it's installed correctly.")
            sys.exit(1)
        
        # Run certbot
        cmd = f"certbot certonly --standalone --preferred-challenges http -d {domain} --email {email} --agree-tos -n"
        returncode, stdout, stderr = run_command(cmd)
        
        if returncode == 0:
            print_debug("SSL certificate obtained successfully")
            break
        
        if i < max_retries - 1:
            print_warning(f"Failed to obtain SSL certificate: {stderr}")
            print_debug("Retrying in 5 seconds...")
            time.sleep(5)
        else:
            print_error(f"Failed to obtain SSL certificate after {max_retries} attempts")
            print_error(f"Error: {stderr}")
            print_error("Please ensure:")
            print_error("1. Your domain points to this server")
            print_error("2. Port 80 is available")
            print_error("3. You have a valid email address")
            sys.exit(1)
    
    # Verify certificate files exist
    cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print_error("SSL certificate files not found after successful generation")
        sys.exit(1)
    
    print_debug("SSL certificate files verified")

def create_conduwuit_config(domain: str, turn_domain: str, secret_key: str, turn_secret: str) -> None:
    """Create Conduwuit configuration file"""
    print_debug("Creating Conduwuit configuration...")
    
    config = f"""# Server configuration
server_name = "{domain}"
database_path = "/data/conduwuit.db"
signing_key = "{secret_key}"
enable_registration = false
report_stats = false

# TURN configuration
[turn]
uris = [
    "turn:{turn_domain}:3478",
    "turns:{turn_domain}:5349"
]
secret = "{turn_secret}"
ttl = 86400

# TLS configuration
[tls]
certs = "/certs/fullchain.pem"
key = "/certs/privkey.pem"
"""
    
    data_dir = Path("/opt/conduwuit/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    with open(data_dir / "conduwuit.yaml", "w") as f:
        f.write(config)

def setup_conduwuit(domain: str, turn_domain: str, email: str, admin_user: str, admin_pass: str) -> None:
    """Setup Conduwuit"""
    install_dir = Path("/opt/conduwuit")
    install_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(install_dir)
    
    # Generate secrets
    secret_key = ''.join(random.choices(string.hexdigits, k=32))
    turn_secret = ''.join(random.choices(string.hexdigits, k=32))
    
    # Create Coturn config
    print_message("Creating Coturn configuration...")
    with open("coturn.conf", "w") as f:
        f.write(f"""use-auth-secret
static-auth-secret={turn_secret}
realm={turn_domain}
# Security
no-tcp-traffic
no-multicast-peers
# TLS support
cert=/certs/fullchain.pem
pkey=/certs/privkey.pem
# Ports
listening-port=3478
tls-listening-port=5349
min-port=49152
max-port=49252
# Logging
verbose
# Other
stale-nonce=0
# External IP (will be auto-detected)
external-ip=auto
""")
    
    # Create docker-compose.yml
    print_message("Creating Docker Compose configuration...")
    with open("docker-compose.yml", "w") as f:
        f.write(f"""services:
  conduwuit:
    image: ghcr.io/girlbossceo/conduwuit:latest
    restart: unless-stopped
    ports:
      - "80:8000"
      - "443:8443"
    volumes:
      - ./data:/data
      - ./certs:/certs
    environment:
      - CONDUWUIT_CONFIG=/data/conduwuit.yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/_matrix/client/versions"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  coturn:
    image: coturn/coturn:latest
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./coturn.conf:/etc/coturn/turnserver.conf:ro
      - ./certs:/certs:ro
    ports:
      - "3478:3478/udp"
      - "3478:3478/tcp"
      - "5349:5349/udp"
      - "5349:5349/tcp"
      - "49152-49252:49152-49252/udp"
    depends_on:
      - conduwuit
""")
    
    # Create Conduwuit config
    create_conduwuit_config(domain, turn_domain, secret_key, turn_secret)
    
    # Get SSL certificates for both domains
    get_ssl_certificate(domain, email)
    get_ssl_certificate(turn_domain, email)
    
    # Copy SSL certificates
    print_debug("Copying SSL certificates...")
    try:
        certs_dir = Path("certs")
        certs_dir.mkdir(exist_ok=True)
        shutil.copy(f"/etc/letsencrypt/live/{domain}/fullchain.pem", certs_dir)
        shutil.copy(f"/etc/letsencrypt/live/{domain}/privkey.pem", certs_dir)
        certs_dir.chmod(0o755)
    except Exception as e:
        print_error(f"Failed to copy SSL certificates: {str(e)}")
        sys.exit(1)
    
    # Start services
    print_message("Starting services...")
    run_command("docker-compose pull")
    run_command("docker-compose up -d")
    
    # Wait for services and check health
    print_debug("Waiting for services to be ready...")
    max_wait_time = 60  # Maximum wait time in seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        # Check container status
        returncode, stdout, stderr = run_command("docker-compose ps -a")
        if "Exit" in stdout or "Restarting" in stdout:
            print_debug("Container is restarting or exited, checking logs...")
            returncode, stdout, stderr = run_command("docker-compose logs conduwuit")
            print_debug(f"Container logs:\n{stdout}")
            time.sleep(5)
            continue
            
        # Try to access the health endpoint
        returncode, stdout, stderr = run_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/_matrix/client/versions")
        if returncode == 0 and stdout.strip() == "200":
            print_debug("Service is healthy and responding")
            break
            
        print_debug("Waiting for service to be ready...")
        time.sleep(5)
    else:
        print_error("Service failed to become healthy within timeout")
        print_debug("Container logs:")
        run_command("docker-compose logs conduwuit")
        sys.exit(1)
    
    # Create admin user
    print_message("Creating admin user...")
    max_retries = 3
    for i in range(max_retries):
        cmd = f"docker-compose exec -T conduwuit register_new_matrix_user -c /data/conduwuit.yaml -u {admin_user} -p {admin_pass} -a"
        returncode, stdout, stderr = run_command(cmd)
        if returncode == 0:
            break
        if i < max_retries - 1:
            print_warning(f"Failed to create admin user (attempt {i+1}/{max_retries}), retrying in 10 seconds...")
            print_debug(f"Error: {stderr}")
            # Check container status and logs
            returncode, stdout, stderr = run_command("docker-compose ps")
            print_debug(f"Container status:\n{stdout}")
            returncode, stdout, stderr = run_command("docker-compose logs --tail=50 conduwuit")
            print_debug(f"Recent container logs:\n{stdout}")
            time.sleep(10)
        else:
            print_error("Failed to create admin user")
            print_error(f"Error: {stderr}")
            print_debug("Container logs:")
            run_command("docker-compose logs conduwuit")
            sys.exit(1)
    
    return secret_key, turn_secret

def main():
    """Main installation function"""
    try:
        check_root()
        check_system()
        check_ports()
        install_packages()
        install_docker()
        install_docker_compose()
        
        domain, turn_domain, email, admin_user, admin_pass = get_user_input()
        secret_key, turn_secret = setup_conduwuit(domain, turn_domain, email, admin_user, admin_pass)
        
        # Print success message
        print_message("\nInstallation complete!")
        print_message(f"Your Conduwuit instance is now running at https://{domain}")
        print_message(f"TURN server is configured at:")
        print_message(f"- turn:{turn_domain}:3478 (UDP/TCP)")
        print_message(f"- turns:{turn_domain}:5349 (TLS)")
        print_message(f"TURN secret: {turn_secret}")
        print("\nAdmin credentials:")
        print(f"Username: {admin_user}")
        print("Password: [HIDDEN]")
        
        print_warning("\nPlease save these credentials in a secure location!")
        print_warning("Make sure both domains point to your server's IP address!")
        
        print("\nManagement commands:")
        print_message("- View logs: docker-compose logs -f")
        print_message("- Stop server: docker-compose down")
        print_message("- Start server: docker-compose up -d")
        print_message("- Restart server: docker-compose restart")
        
        print_debug("\nIf you experience any issues, please check the logs using: docker-compose logs")
        
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Installation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 