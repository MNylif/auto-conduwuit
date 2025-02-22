# Auto-Conduwuit Install

This is an automated installation script for setting up a Conduwuit server using Docker. The script handles all necessary dependencies, SSL certificate generation, and server configuration.

## Quick Start

To install Conduwuit, run this command:

```bash
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

## Requirements

- A VPS or server running Ubuntu/Debian
- A domain name pointing to your server
- Root/sudo access
- Port 80 and 443 available

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
- All credentials are collected securely

## Support

For issues or questions, please visit:
- [Conduwuit Documentation](https://conduwuit.puppyirl.gay/)
- [GitHub Issues](https://github.com/MNylif/auto-conduwuit/issues) 