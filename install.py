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
    packages = [
        'apt-transport-https',
        'ca-certificates',
        'curl',
        'gnupg',
        'lsb-release',
        'software-properties-common',
        'net-tools'
    ]
    
    # Update package list
    cmd = f"apt-get update"
    returncode, stdout, stderr = run_command(cmd)
    if returncode != 0:
        print_error(f"Failed to update package list: {stderr}")
        sys.exit(1)

    # Install packages
    cmd = f"apt-get install -y {' '.join(packages)}"
    returncode, stdout, stderr = run_command(cmd)
    if returncode != 0:
        print_error(f"Failed to install packages: {stderr}")
        sys.exit(1)

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
    
    # Verify domain resolves
    print_debug("Verifying domain DNS...")
    try:
        socket.gethostbyname(domain)
    except socket.gaierror:
        print_warning(f"Unable to resolve domain {domain}")
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
    
    return domain, email, admin_user, admin_pass

def setup_conduwuit(domain: str, email: str, admin_user: str, admin_pass: str) -> None:
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
realm={domain}
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
""")
    
    # Create docker-compose.yml
    print_message("Creating Docker Compose configuration...")
    with open("docker-compose.yml", "w") as f:
        f.write(f"""version: '3'

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
      - CONDUWUIT_SERVER_NAME={domain}
      - CONDUWUIT_REPORT_STATS=false
      - CONDUWUIT_DATABASE_PATH=/data/conduwuit.db
      - CONDUWUIT_SIGNING_KEY={secret_key}
      - CONDUWUIT_ENABLE_REGISTRATION=false
      - CONDUWUIT_TURN_URI=turn:{domain}:3478
      - CONDUWUIT_TURN_SECRET={turn_secret}
      - CONDUWUIT_TURN_TTL=86400

  coturn:
    image: coturn/coturn:latest
    restart: always
    network_mode: host
    volumes:
      - ./coturn.conf:/etc/coturn/turnserver.conf:ro
    depends_on:
      - conduwuit
""")
    
    # Get SSL certificate
    print_message("Obtaining SSL certificate...")
    cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos -n"
    returncode, stdout, stderr = run_command(cmd)
    if returncode != 0:
        print_error(f"SSL certificate generation failed: {stderr}")
        sys.exit(1)
    
    # Copy SSL certificates
    certs_dir = Path("certs")
    certs_dir.mkdir(exist_ok=True)
    shutil.copy(f"/etc/letsencrypt/live/{domain}/fullchain.pem", certs_dir)
    shutil.copy(f"/etc/letsencrypt/live/{domain}/privkey.pem", certs_dir)
    certs_dir.chmod(0o755)
    
    # Start services
    print_message("Starting services...")
    run_command("docker-compose pull")
    run_command("docker-compose up -d")
    
    # Wait for services
    print_debug("Waiting for services to be ready...")
    time.sleep(10)
    
    # Verify services
    returncode, stdout, stderr = run_command("docker-compose ps")
    if "Up" not in stdout:
        print_error("Services failed to start")
        print_debug("Container logs:")
        run_command("docker-compose logs")
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
            print_warning("Failed to create admin user, retrying...")
            time.sleep(5)
        else:
            print_error("Failed to create admin user")
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
        
        domain, email, admin_user, admin_pass = get_user_input()
        secret_key, turn_secret = setup_conduwuit(domain, email, admin_user, admin_pass)
        
        # Print success message
        print_message("\nInstallation complete!")
        print_message(f"Your Conduwuit instance is now running at https://{domain}")
        print_message(f"TURN server is configured at turn:{domain}:3478")
        print_message(f"TURN secret: {turn_secret}")
        print("\nAdmin credentials:")
        print(f"Username: {admin_user}")
        print("Password: [HIDDEN]")
        
        print_warning("\nPlease save these credentials in a secure location!")
        
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