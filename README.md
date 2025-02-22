# Auto-Conduwuit Install

This is an automated installation script for setting up a Conduwuit server using Docker. The script handles all necessary dependencies, SSL certificate generation, and server configuration.

## Quick Start

To install Conduwuit, run this command:

```bash
curl -fsSL https://raw.githubusercontent.com/MNylif/auto-conduwuit/main/install.py -o install.py && sudo python3 install.py
```

## What the Script Does

1. Checks system requirements and port availability
2. Installs system dependencies (including certbot)
3. Installs and configures Docker
4. Installs Docker Compose
5. Obtains SSL certificates via Let's Encrypt
6. Sets up Conduwuit with Docker
7. Creates admin account
8. Installs and configures Coturn TURN server for voice/video calls

## Requirements

- A VPS or server running Ubuntu/Debian
- Python 3.6+
- A domain name pointing to your server
- Root/sudo access
- Port 80 and 443 available for HTTPS
- Ports 3478 (TURN) and 49152-49252 (RTP) available for voice/video calls

## Features

- Automated dependency installation
- Secure configuration out of the box
- Automatic SSL certificate generation
- TURN server for voice/video calls
- Docker-based deployment
- Detailed progress information
- Comprehensive error handling

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

## Security Features

- SSL certificates automatically obtained and configured
- Admin registration disabled by default
- Secure random signing key generated
- TURN server configured with authentication
- All credentials collected securely
- Proper file permissions
- Safe secret handling

## Error Handling

The script includes robust error handling:
- Pre-flight system checks
- Port availability verification
- Package installation verification
- SSL certificate generation retries
- Service health checks
- Detailed error messages
- Automatic retry mechanisms

## Troubleshooting

If you encounter issues:

1. Check the logs using `docker-compose logs`
2. Ensure all required ports are available
3. Verify your domain points to the server
4. Make sure you have Python 3.6+ installed
5. Run the script with sudo/root privileges

## Support

For issues or questions, please visit:
- [Conduwuit Documentation](https://conduwuit.puppyirl.gay/)
- [GitHub Issues](https://github.com/MNylif/auto-conduwuit/issues) 