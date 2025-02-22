# Auto-Conduwuit Install

This is an automated installation script for setting up a Conduwuit server using Docker. The script handles all necessary dependencies, SSL certificate generation, and server configuration.

## Quick Start

To install Conduwuit, you can use either the Python script (recommended) or shell script:

```bash
# Using Python (Recommended)
curl -fsSL https://raw.githubusercontent.com/MNylif/auto-conduwuit/main/install.py -o install.py && sudo python3 install.py

# Using Shell Script (Legacy)
curl -fsSL https://raw.githubusercontent.com/MNylif/auto-conduwuit/main/install.sh | sudo bash
```

## What the Script Does

1. Installs system dependencies
2. Installs and configures Docker
3. Installs Docker Compose
4. Installs Certbot for SSL certificates
5. Sets up Conduwuit with Docker
6. Configures SSL certificates
7. Creates admin account
8. Installs and configures Coturn TURN server for voice/video calls

## Requirements

- A VPS or server running Ubuntu/Debian
- Python 3.6+ (for Python installer)
- A domain name pointing to your server
- Root/sudo access
- Port 80 and 443 available for HTTPS
- Ports 3478 (TURN) and 49152-49252 (RTP) available for voice/video calls

## Interactive Prompts

The script will ask for:

1. Domain name for your Conduwuit instance
2. Email address for SSL certificate
3. Admin username
4. Admin password

## Post-Installation

After installation, your Conduwuit instance will be:

- Running at `https://your-domain.com`
- Configured with SSL
- TURN server running at `turn:your-domain.com:3478`
- Ready to use with your admin account

## Management Commands

- View logs: `docker-compose logs -f`
- Stop server: `docker-compose down`
- Start server: `docker-compose up -d`
- Restart server: `docker-compose restart`

## Security

- SSL certificates are automatically obtained and configured
- Admin registration is disabled by default
- Secure random signing key is generated
- TURN server configured with authentication
- All credentials are collected securely

## Advantages of Python Installer

- Better error handling and debugging
- No interactive package prompts
- Automatic retry mechanisms
- More detailed progress information
- Better system requirement checks
- Proper port availability verification
- Improved service health checks

## Support

For issues or questions, please visit:
- [Conduwuit Documentation](https://conduwuit.puppyirl.gay/)
- [GitHub Issues](https://github.com/MNylif/auto-conduwuit/issues) 