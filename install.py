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
import requests
import threading
import queue
import datetime

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
        'curl',
        'python3-requests'  # Added for IP detection
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

def print_progress(iteration, total, prefix='', suffix='', length=50, fill='█'):
    """Print a progress bar"""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if iteration == total:
        print()

def kill_stuck_process(process_name: str) -> bool:
    """Attempt to kill a stuck process"""
    print_warning(f"Attempting to kill stuck {process_name} process...")
    returncode, stdout, stderr = run_command(f"pkill {process_name}")
    if returncode == 0:
        print_message(f"Successfully killed {process_name} process")
        return True
    return False

def check_and_fix_locks():
    """Check for and attempt to fix package manager locks"""
    lock_files = [
        "/var/lib/dpkg/lock-frontend",
        "/var/lib/apt/lists/lock",
        "/var/lib/dpkg/lock"
    ]
    
    for lock_file in lock_files:
        if os.path.exists(lock_file):
            print_warning(f"Removing lock file: {lock_file}")
            try:
                os.remove(lock_file)
                print_message(f"Successfully removed {lock_file}")
            except Exception as e:
                print_error(f"Failed to remove {lock_file}: {str(e)}")

def install_docker() -> None:
    """Install Docker"""
    print_message("Installing Docker...")
    
    # Wait for any package manager locks
    def check_package_locks():
        lock_files = [
            "/var/lib/dpkg/lock-frontend",
            "/var/lib/apt/lists/lock",
            "/var/lib/dpkg/lock"
        ]
        processes = ["unattended-upgr", "apt-get", "dpkg"]
        
        # Check for lock files
        for lock_file in lock_files:
            if os.path.exists(lock_file):
                print_warning(f"Package manager lock file found: {lock_file}")
                return True
                
        # Check for running processes
        for proc in processes:
            returncode, stdout, stderr = run_command(f"pgrep {proc}")
            if returncode == 0:
                print_warning(f"Package manager process running: {proc}")
                return True
        return False
    
    # Wait for package manager to be available
    max_wait_time = 300  # 5 minutes
    check_interval = 5  # Check every 5 seconds
    total_checks = max_wait_time // check_interval
    start_time = time.time()
    consecutive_same_state = 0
    last_state = None
    
    for i in range(total_checks):
        current_time = time.time() - start_time
        current_state = check_package_locks()
        
        # Print progress
        print_progress(i + 1, total_checks, 
                      prefix='Waiting for package manager:', 
                      suffix=f'Time elapsed: {int(current_time)}s')
        
        if not current_state:
            print_message("\nPackage manager is now available")
            break
            
        # Check if state hasn't changed
        if current_state == last_state:
            consecutive_same_state += 1
        else:
            consecutive_same_state = 0
        
        # If stuck in same state for too long, try to fix
        if consecutive_same_state >= 6:  # 30 seconds in same state
            print_warning("\nPackage manager appears to be stuck")
            
            # Try to fix the situation
            if kill_stuck_process("unattended-upgr"):
                time.sleep(2)
            if kill_stuck_process("dpkg"):
                time.sleep(2)
            check_and_fix_locks()
            
            # Ask user what to do
            print_warning("\nOptions:")
            print("1. Continue waiting")
            print("2. Try to force remove locks")
            print("3. Exit and try again later")
            
            choice = input("Choose an option (1-3): ").strip()
            if choice == "2":
                check_and_fix_locks()
                # Wait a bit after fixing locks
                time.sleep(5)
            elif choice == "3":
                print_error("Installation cancelled by user")
                sys.exit(1)
            
            consecutive_same_state = 0
        
        last_state = current_state
        time.sleep(check_interval)
        
    if check_package_locks():
        print_error("\nTimeout waiting for package manager locks to be released")
        print_error("Please try these steps:")
        print_error("1. Wait a few minutes and try again")
        print_error("2. Run these commands to fix stuck locks:")
        print_error("   sudo killall apt apt-get dpkg unattended-upgr")
        print_error("   sudo rm /var/lib/dpkg/lock*")
        print_error("   sudo rm /var/lib/apt/lists/lock")
        print_error("   sudo dpkg --configure -a")
        sys.exit(1)
    
    # Download Docker install script
    print_debug("Downloading Docker install script...")
    try:
        urllib.request.urlretrieve("https://get.docker.com", "get-docker.sh")
    except Exception as e:
        print_error(f"Failed to download Docker install script: {str(e)}")
        sys.exit(1)
    
    # Install Docker with retry logic and progress indicator
    print_debug("Installing Docker...")
    max_retries = 3
    for i in range(max_retries):
        print_message(f"Docker installation attempt {i+1}/{max_retries}")
        
        process = subprocess.Popen(
            ["sh", "get-docker.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print_debug(output.strip())
        
        returncode = process.poll()
        if returncode == 0:
            break
            
        if i < max_retries - 1:
            print_warning(f"Docker installation attempt {i+1} failed. Retrying in 10 seconds...")
            time.sleep(10)
        else:
            print_error("Docker installation failed after multiple attempts")
            print_error("Please try installing Docker manually:")
            print_error("curl -fsSL https://get.docker.com | sudo sh")
            sys.exit(1)
    
    # Start Docker service with progress indicator
    print_debug("Starting Docker service...")
    max_wait = 30
    for i in range(max_wait):
        print_progress(i + 1, max_wait, prefix='Starting Docker service:', suffix='Please wait...')
        returncode, stdout, stderr = run_command("systemctl is-active docker")
        if returncode == 0:
            print_message("\nDocker service started successfully")
            break
        run_command("systemctl start docker")
        time.sleep(1)
    else:
        print_error("\nFailed to start Docker service")
        print_error("Please check Docker service status:")
        print_error("sudo systemctl status docker")
        sys.exit(1)
    
    # Enable Docker service
    run_command("systemctl enable docker")
    
    # Clean up install script
    try:
        os.remove("get-docker.sh")
    except:
        pass

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
        domain = input("Enter your main domain (e.g., example.com): ").strip()
        if domain:
            break
        print_error("Domain name cannot be empty")
    
    # Set subdomains
    matrix_domain = f"matrix.{domain}"
    turn_domain = f"turn.{domain}"
    
    # Get server IP
    try:
        ip = requests.get('https://api.ipify.org').text.strip()
    except:
        ip = input("Enter your server's public IP address: ").strip()
    
    # Print DNS setup instructions
    print_message("\nDNS Setup Instructions:")
    print_message("Please create the following A records in your DNS settings:")
    print(f"  matrix.{domain}  A     {ip}")
    print(f"  turn.{domain}    A     {ip}")
    
    print_warning("\nIf you're using Cloudflare:")
    print("1. Set SSL/TLS encryption mode to 'Full (strict)'")
    print("2. Create the following DNS records:")
    print(f"  matrix.{domain}  A     {ip}  (Proxy status: DNS only/Grey cloud)")
    print(f"  turn.{domain}    A     {ip}  (Proxy status: DNS only/Grey cloud)")
    print("3. Create the following Page Rules:")
    print(f"  URL: matrix.{domain}/*")
    print("  Settings: SSL: Full")
    
    print_warning("\nIf you're using another reverse proxy:")
    print("1. Ensure WebSocket support is enabled")
    print("2. Configure SSL passthrough or terminate SSL and provide valid certificates")
    print("3. Forward all traffic to the Conduwuit container")
    print("4. Do not proxy TURN server traffic (ports 3478, 5349, 49152-49252)")
    
    if input("\nHave you configured these DNS records? (y/N): ").lower() != 'y':
        print_warning("Please configure DNS records before continuing")
        if input("Continue anyway? (y/N): ").lower() != 'y':
            sys.exit(1)
    
    # Verify domains resolve
    print_debug("Verifying domain DNS...")
    try:
        resolved_ip = socket.gethostbyname(matrix_domain)
        if resolved_ip != ip:
            print_warning(f"Warning: {matrix_domain} resolves to {resolved_ip}, but your server IP is {ip}")
        resolved_ip = socket.gethostbyname(turn_domain)
        if resolved_ip != ip:
            print_warning(f"Warning: {turn_domain} resolves to {resolved_ip}, but your server IP is {ip}")
    except socket.gaierror:
        print_warning(f"Unable to resolve {matrix_domain} or {turn_domain}")
        print_warning("DNS records may not have propagated yet")
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
    
    return matrix_domain, turn_domain, email, admin_user, admin_pass

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
    
    config = f"""[global]
server_name = "{domain}"
database_path = "/data/conduwuit.db"
signing_key = "{secret_key}"
enable_registration = false
report_stats = false

[turn]
uris = [
    "turn:{turn_domain}:3478",
    "turns:{turn_domain}:5349"
]
secret = "{turn_secret}"
ttl = 86400

[tls]
certs = "/certs/fullchain.pem"
key = "/certs/privkey.pem"
"""
    
    data_dir = Path("/opt/conduwuit/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with .toml extension instead of .yaml
    with open(data_dir / "conduwuit.toml", "w") as f:
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
      - CONDUWUIT_CONFIG=/data/conduwuit.toml
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
        cmd = f"docker-compose exec -T conduwuit register_new_matrix_user -c /data/conduwuit.toml -u {admin_user} -p {admin_pass} -a"
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

class InstallationProgress:
    def __init__(self):
        self.current_step = 0
        self.total_steps = 10  # Total number of main installation steps
        self.current_operation = ""
        self.start_time = datetime.datetime.now()
        self._stop_spinner = False
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_idx = 0
        
    def update_step(self, step: int, operation: str):
        self.current_step = step
        self.current_operation = operation
        self.show_progress()
    
    def show_progress(self):
        elapsed = datetime.datetime.now() - self.start_time
        percent = (self.current_step / self.total_steps) * 100
        print(f"\r{Colors.BLUE}[*]{Colors.NC} Progress: [{self.current_step}/{self.total_steps}] {percent:.1f}% - {self.current_operation}")
        print(f"{Colors.BLUE}[*]{Colors.NC} Time elapsed: {str(elapsed).split('.')[0]}")

    def start_spinner(self, message: str):
        self._stop_spinner = False
        threading.Thread(target=self._spin, args=(message,), daemon=True).start()
    
    def stop_spinner(self):
        self._stop_spinner = True
        time.sleep(0.1)  # Give spinner time to stop
        print()  # New line after spinner stops
    
    def _spin(self, message: str):
        while not self._stop_spinner:
            print(f"\r{Colors.BLUE}[{self.spinner_chars[self.spinner_idx]}]{Colors.NC} {message}", end="")
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            time.sleep(0.1)

class TroubleshootingMenu:
    def __init__(self):
        self.progress = None
    
    def set_progress(self, progress: InstallationProgress):
        self.progress = progress
    
    def show_menu(self, context: str, logs_cmd: str = None) -> bool:
        """Show troubleshooting menu and return whether to continue"""
        print_warning(f"\nOperation taking longer than expected: {context}")
        print("\nTroubleshooting Options:")
        print("1. Continue waiting")
        print("2. View logs/diagnostics")
        print("3. Attempt automatic fix")
        print("4. Cancel installation")
        
        while True:
            choice = input("\nChoose an option (1-4): ").strip()
            
            if choice == "1":
                return True
            elif choice == "2":
                self._show_diagnostics(context, logs_cmd)
                return self.show_menu(context, logs_cmd)  # Show menu again after viewing logs
            elif choice == "3":
                if self._attempt_fix(context):
                    return True
                return self.show_menu(context, logs_cmd)  # Show menu again if fix wasn't successful
            elif choice == "4":
                if input("Are you sure you want to cancel? (y/N): ").lower() == 'y':
                    print_error("Installation cancelled by user")
                    sys.exit(1)
            else:
                print_error("Invalid choice")
    
    def _show_diagnostics(self, context: str, logs_cmd: str = None):
        """Show relevant logs and diagnostics"""
        print_debug("\nGathering diagnostic information...")
        
        if logs_cmd:
            print_debug(f"Logs for {context}:")
            returncode, stdout, stderr = run_command(logs_cmd)
            print(stdout)
        
        print_debug("\nSystem Status:")
        run_command("free -h")  # Memory usage
        run_command("df -h")    # Disk usage
        run_command("top -b -n 1 | head -n 20")  # Process status
        
        input("\nPress Enter to continue...")
    
    def _attempt_fix(self, context: str) -> bool:
        """Attempt to automatically fix common issues"""
        print_debug(f"Attempting to fix issues with {context}...")
        
        if "package manager" in context.lower():
            return self._fix_package_manager()
        elif "docker" in context.lower():
            return self._fix_docker()
        elif "certbot" in context.lower():
            return self._fix_certbot()
        elif "conduwuit" in context.lower():
            return self._fix_conduwuit()
        
        print_warning("No automatic fix available for this issue")
        return False
    
    def _fix_package_manager(self) -> bool:
        """Fix common package manager issues"""
        print_debug("Attempting to fix package manager...")
        
        # Kill stuck processes
        processes = ["unattended-upgr", "apt-get", "dpkg"]
        for proc in processes:
            kill_stuck_process(proc)
        
        # Remove lock files
        check_and_fix_locks()
        
        # Reconfigure packages
        run_command("dpkg --configure -a")
        
        return True
    
    def _fix_docker(self) -> bool:
        """Fix common Docker issues"""
        print_debug("Attempting to fix Docker...")
        
        run_command("systemctl restart docker")
        time.sleep(2)
        
        returncode, stdout, stderr = run_command("systemctl is-active docker")
        return returncode == 0
    
    def _fix_certbot(self) -> bool:
        """Fix common Certbot issues"""
        print_debug("Attempting to fix Certbot...")
        
        run_command("snap remove certbot")
        time.sleep(2)
        run_command("snap install --classic certbot")
        run_command("ln -sf /snap/bin/certbot /usr/bin/certbot")
        
        returncode, stdout, stderr = run_command("which certbot")
        return returncode == 0
    
    def _fix_conduwuit(self) -> bool:
        """Fix common Conduwuit issues"""
        print_debug("Attempting to fix Conduwuit...")
        
        run_command("docker-compose down")
        time.sleep(2)
        run_command("docker-compose up -d")
        
        return True

# Initialize global progress tracker and troubleshooting menu
progress = InstallationProgress()
troubleshoot = TroubleshootingMenu()
troubleshoot.set_progress(progress)

def wait_for_operation(operation: str, check_func, timeout: int = 60, check_interval: int = 5, logs_cmd: str = None) -> bool:
    """Wait for an operation to complete with progress tracking and troubleshooting"""
    start_time = time.time()
    progress.start_spinner(f"Waiting for {operation}...")
    
    while time.time() - start_time < timeout:
        if check_func():
            progress.stop_spinner()
            return True
            
        if time.time() - start_time > timeout // 2:  # Show menu after half the timeout
            progress.stop_spinner()
            if not troubleshoot.show_menu(operation, logs_cmd):
                return False
            progress.start_spinner(f"Continuing to wait for {operation}...")
            
        time.sleep(check_interval)
    
    progress.stop_spinner()
    return False

def main():
    """Main installation function"""
    try:
        # Initialize progress
        progress.update_step(0, "Starting installation")
        
        # System checks
        progress.update_step(1, "Checking system requirements")
        check_root()
        check_system()
        check_ports()
        
        # Package installation
        progress.update_step(2, "Installing required packages")
        install_packages()
        
        # Docker installation
        progress.update_step(3, "Installing Docker")
        install_docker()
        
        # Docker Compose installation
        progress.update_step(4, "Installing Docker Compose")
        install_docker_compose()
        
        # Get user input
        progress.update_step(5, "Configuring installation")
        matrix_domain, turn_domain, email, admin_user, admin_pass = get_user_input()
        
        # Setup Conduwuit
        progress.update_step(6, "Setting up Conduwuit")
        secret_key, turn_secret = setup_conduwuit(matrix_domain, turn_domain, email, admin_user, admin_pass)
        
        # Wait for services
        progress.update_step(7, "Waiting for services to start")
        def check_services():
            returncode, stdout, stderr = run_command("docker-compose ps -a")
            if "Exit" in stdout or "Restarting" in stdout:
                return False
            returncode, stdout, stderr = run_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/_matrix/client/versions")
            return returncode == 0 and stdout.strip() == "200"
        
        if not wait_for_operation(
            "services to become healthy",
            check_services,
            timeout=120,
            check_interval=5,
            logs_cmd="docker-compose logs --tail=50"
        ):
            print_error("Services failed to start properly")
            sys.exit(1)
        
        # Create admin user
        progress.update_step(8, "Creating admin user")
        def check_admin_user():
            cmd = f"docker-compose exec -T conduwuit register_new_matrix_user -c /data/conduwuit.toml -u {admin_user} -p {admin_pass} -a"
            returncode, stdout, stderr = run_command(cmd)
            return returncode == 0
        
        if not wait_for_operation(
            "admin user creation",
            check_admin_user,
            timeout=60,
            check_interval=5,
            logs_cmd="docker-compose logs conduwuit"
        ):
            print_error("Failed to create admin user")
            sys.exit(1)
        
        # Final verification
        progress.update_step(9, "Verifying installation")
        def check_final():
            # Check if services are running
            returncode, stdout, stderr = run_command("docker-compose ps -a")
            if "Exit" in stdout or "Restarting" in stdout:
                return False
            # Check if we can access the server
            returncode, stdout, stderr = run_command(f"curl -sk https://{matrix_domain}/_matrix/client/versions")
            return returncode == 0
        
        if not wait_for_operation(
            "final verification",
            check_final,
            timeout=30,
            check_interval=5,
            logs_cmd="docker-compose logs"
        ):
            print_error("Final verification failed")
            sys.exit(1)
        
        # Installation complete
        progress.update_step(10, "Installation complete")
        
        # Print success message
        print_message("\nInstallation complete!")
        print_message(f"Your Conduwuit instance is now running at https://{matrix_domain}")
        print_message(f"TURN server is configured at:")
        print_message(f"- turn:{turn_domain}:3478 (UDP/TCP)")
        print_message(f"- turns:{turn_domain}:5349 (TLS)")
        print_message(f"TURN secret: {turn_secret}")
        print("\nAdmin credentials:")
        print(f"Username: {admin_user}")
        print("Password: [HIDDEN]")
        
        print_warning("\nPlease save these credentials in a secure location!")
        print_warning("Make sure your DNS records are properly configured:")
        print(f"  matrix.* → {matrix_domain}")
        print(f"  turn.*  → {turn_domain}")
        
        if input("\nWould you like to see the DNS and proxy setup instructions again? (y/N): ").lower() == 'y':
            print_message("\nDNS Setup Instructions:")
            print("Please ensure these A records exist in your DNS settings:")
            print(f"  {matrix_domain}  A     <your-server-ip>")
            print(f"  {turn_domain}    A     <your-server-ip>")
            
            print_warning("\nIf you're using Cloudflare:")
            print("1. Set SSL/TLS encryption mode to 'Full (strict)'")
            print("2. Ensure both domains are set to DNS only (grey cloud)")
            print("3. Configure these page rules:")
            print(f"  URL: {matrix_domain}/*")
            print("  Settings: SSL: Full")
            
            print_warning("\nIf you're using another reverse proxy:")
            print("1. Enable WebSocket support")
            print("2. Configure SSL properly")
            print("3. Forward matrix traffic to the Conduwuit container")
            print("4. Do not proxy TURN server traffic")
        
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