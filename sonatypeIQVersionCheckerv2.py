#!/usr/bin/env python3
"""
Sonatype IQ Server Version Checker

Monitors the Sonatype IQ Server release notes page for new versions and sends
notifications via email and/or Slack when a new version is detected.

Configuration (in order of precedence):
    1. Command-line arguments
    2. Environment variables
    3. .env file
    4. Default values

Environment Variables / .env file:
    - SMTP_SERVER (default: smtp.office365.com)
    - SMTP_PORT (default: 587)
    - EMAIL_USERNAME (required if email enabled)
    - EMAIL_PASSWORD (required if email enabled)
    - EMAIL_FROM (required if email enabled)
    - EMAIL_TO (required if email enabled)
    - SLACK_WEBHOOK_URL (required if Slack enabled)
    - VERSION_FILE (default: sonatype_last_version.txt)
    - ENABLE_EMAIL (default: false)
    - ENABLE_SLACK (default: false)
    - DRY_RUN (default: false)

Usage:
    # Using command-line arguments
    python sonatype_version_checker.py --enable-email --email-username user@example.com
    
    # Using environment variables
    export EMAIL_USERNAME="user@example.com"
    python sonatype_version_checker.py --enable-email
    
    # Using .env file (requires python-dotenv: pip install python-dotenv)
    # Create a .env file with your configuration, then run:
    python sonatype_version_checker.py --enable-slack
    
    # Dry run to test without sending notifications
    python sonatype_version_checker.py --dry-run --enable-email --enable-slack

Command-line Arguments:
    --enable-email              Enable email notifications (default: disabled)
    --enable-slack              Enable Slack notifications (default: disabled)
    --disable-email             Explicitly disable email notifications
    --disable-slack             Explicitly disable Slack notifications
    --smtp-server SERVER        SMTP server hostname
    --smtp-port PORT            SMTP server port
    --email-username USERNAME   Email account username
    --email-password PASSWORD   Email account password
    --email-from ADDRESS        From email address
    --email-to ADDRESS          To email address
    --slack-webhook URL         Slack webhook URL
    --version-file PATH         Path to version tracking file
    --dry-run                   Run without sending notifications
    --verbose                   Enable verbose logging
"""

import os
import re
import sys
import smtplib
import logging
import argparse
import time
import requests
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip .env file loading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
URL = 'https://help.sonatype.com/en/iq-server-release-notes.html'
VERSION_PATTERN = r"\b\d{3}\b"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 5


class ConfigError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class Config:
    """Configuration manager with validation"""
    
    def __init__(self, args):
        """
        Initialize configuration from args, environment variables, and defaults
        
        Args:
            args: Parsed command-line arguments from argparse
        """
        # SMTP configuration
        self.smtp_server = args.smtp_server or os.getenv('SMTP_SERVER', 'smtp.office365.com')
        self.smtp_port = args.smtp_port or int(os.getenv('SMTP_PORT', '587'))
        
        # Email configuration
        self.email_username = args.email_username or os.getenv('EMAIL_USERNAME')
        self.email_password = args.email_password or os.getenv('EMAIL_PASSWORD')
        self.email_from = args.email_from or os.getenv('EMAIL_FROM')
        self.email_to = args.email_to or os.getenv('EMAIL_TO')
        
        # Slack configuration
        self.slack_webhook_url = args.slack_webhook or os.getenv('SLACK_WEBHOOK_URL')
        
        # File configuration
        self.version_file = args.version_file or os.getenv('VERSION_FILE', 'sonatype_last_version.txt')
        
        # Feature flags - command line args take precedence
        if args.enable_email:
            self.enable_email = True
        elif args.disable_email:
            self.enable_email = False
        else:
            self.enable_email = os.getenv('ENABLE_EMAIL', 'false').lower() == 'true'
        
        if args.enable_slack:
            self.enable_slack = True
        elif args.disable_slack:
            self.enable_slack = False
        else:
            self.enable_slack = os.getenv('ENABLE_SLACK', 'false').lower() == 'true'
        
        self.dry_run = args.dry_run or os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    def validate(self):
        """Validate configuration and raise ConfigError if invalid"""
        errors = []
        
        if self.enable_email:
            if not self.email_username:
                errors.append("EMAIL_USERNAME is required when email is enabled")
            if not self.email_password:
                errors.append("EMAIL_PASSWORD is required when email is enabled")
            if not self.email_from:
                errors.append("EMAIL_FROM is required when email is enabled")
            if not self.email_to:
                errors.append("EMAIL_TO is required when email is enabled")
        
        if self.enable_slack:
            if not self.slack_webhook_url:
                errors.append("SLACK_WEBHOOK_URL is required when Slack is enabled")
            elif not self.slack_webhook_url.startswith('https://hooks.slack.com/'):
                errors.append("SLACK_WEBHOOK_URL appears to be invalid")
        
        if not self.enable_email and not self.enable_slack:
            errors.append("At least one notification method must be enabled. Use --enable-email or --enable-slack")
        
        if errors:
            raise ConfigError("Configuration validation failed:\n  - " + "\n  - ".join(errors))
        
        logger.info("Configuration validated successfully")
        logger.info(f"Email notifications: {'enabled' if self.enable_email else 'disabled'}")
        logger.info(f"Slack notifications: {'enabled' if self.enable_slack else 'disabled'}")


def sanitize_version(version: str) -> str:
    """Sanitize version string to prevent injection attacks"""
    # Only allow digits and dots
    sanitized = re.sub(r'[^\d.]', '', version)
    if sanitized != version:
        logger.warning(f"Version string sanitized: '{version}' -> '{sanitized}'")
    return sanitized


def get_latest_version(retry_count: int = 0) -> Optional[str]:
    """
    Fetch the latest version from the Sonatype website
    
    Args:
        retry_count: Current retry attempt number
        
    Returns:
        Latest version string or None if not found
    """
    try:
        logger.info(f"Fetching page from {URL}")
        response = requests.get(
            URL,
            timeout=REQUEST_TIMEOUT,
            headers={'User-Agent': 'Sonatype-Version-Checker/2.0'}
        )
        response.raise_for_status()
        
        matches = re.findall(VERSION_PATTERN, response.text)
        if matches:
            latest_version = str(max(map(int, matches)))
            sanitized = sanitize_version(latest_version)
            logger.info(f"Found latest version: {sanitized}")
            return sanitized
        else:
            logger.warning("No version found in page content")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out after {REQUEST_TIMEOUT} seconds")
        if retry_count < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return get_latest_version(retry_count + 1)
        logger.error("Max retries reached")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching page: {e}")
        if retry_count < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return get_latest_version(retry_count + 1)
        logger.error("Max retries reached")
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return None


def read_last_version(version_file: str) -> Optional[str]:
    """Read the last known version from file"""
    try:
        with open(version_file, 'r') as f:
            version = f.read().strip()
            logger.debug(f"Read last version: {version}")
            return version
    except FileNotFoundError:
        logger.info("No previous version file found - this appears to be the first run")
        return None
    except Exception as e:
        logger.error(f"Error reading version file: {e}")
        return None


def write_last_version(version: str, version_file: str) -> bool:
    """Write the current version to file"""
    try:
        with open(version_file, 'w') as f:
            f.write(version)
        logger.debug(f"Wrote version {version} to file")
        return True
    except Exception as e:
        logger.error(f"Error writing version file: {e}")
        return False


def send_email_notification(config: Config, version: str) -> bool:
    """
    Send email notification about new version
    
    Returns:
        True if successful, False otherwise
    """
    if config.dry_run:
        logger.info(f"[DRY RUN] Would send email to {config.email_to}")
        return True
    
    msg = MIMEMultipart()
    msg['From'] = config.email_from
    msg['To'] = config.email_to
    msg['Subject'] = f"New Sonatype IQ Server Version Detected: {version}"
    
    body = f"""A new version of the Sonatype IQ Server has been released.

Version: {version}
Release Notes: {URL}

This is an automated notification from the Sonatype Version Checker.
"""
    msg.attach(MIMEText(body, 'plain'))

    try:
        logger.info("Sending email notification...")
        with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(config.email_username, config.email_password)
            server.sendmail(config.email_from, config.email_to, msg.as_string())
        logger.info("Email notification sent successfully")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Email authentication failed - check EMAIL_USERNAME and EMAIL_PASSWORD")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False


def send_slack_notification(config: Config, version: str) -> bool:
    """
    Send Slack notification about new version
    
    Returns:
        True if successful, False otherwise
    """
    if config.dry_run:
        logger.info("[DRY RUN] Would send Slack notification")
        return True
    
    payload = {
        "text": f":tada: New Sonatype IQ Server version detected: *{version}*\nCheck release notes: {URL}"
    }
    
    try:
        logger.info("Sending Slack notification...")
        response = requests.post(
            config.slack_webhook_url,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.error(f"Slack API returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Slack notification: {e}")
        return False


def notify_new_version(config: Config, version: str) -> bool:
    """
    Send all configured notifications
    
    Returns:
        True if at least one notification succeeded
    """
    logger.info(f"New version detected: {version}")
    
    success = False
    
    if config.enable_email:
        if send_email_notification(config, version):
            success = True
    
    if config.enable_slack:
        if send_slack_notification(config, version):
            success = True
    
    return success


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Monitor Sonatype IQ Server for new versions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enable email notifications via command line
  %(prog)s --enable-email --email-username user@example.com --email-password secret
  
  # Enable both email and Slack
  %(prog)s --enable-email --enable-slack
  
  # Test without sending notifications
  %(prog)s --dry-run --enable-email --enable-slack
  
  # Use environment variables (set EMAIL_USERNAME, etc. first)
  %(prog)s --enable-email
        """
    )
    
    # Notification control
    parser.add_argument(
        '--enable-email',
        action='store_true',
        help='Enable email notifications (default: disabled)'
    )
    parser.add_argument(
        '--enable-slack',
        action='store_true',
        help='Enable Slack notifications (default: disabled)'
    )
    parser.add_argument(
        '--disable-email',
        action='store_true',
        help='Explicitly disable email notifications'
    )
    parser.add_argument(
        '--disable-slack',
        action='store_true',
        help='Explicitly disable Slack notifications'
    )
    
    # SMTP configuration
    parser.add_argument(
        '--smtp-server',
        help='SMTP server hostname (default: smtp.office365.com)'
    )
    parser.add_argument(
        '--smtp-port',
        type=int,
        help='SMTP server port (default: 587)'
    )
    
    # Email configuration
    parser.add_argument(
        '--email-username',
        help='Email account username'
    )
    parser.add_argument(
        '--email-password',
        help='Email account password'
    )
    parser.add_argument(
        '--email-from',
        help='From email address'
    )
    parser.add_argument(
        '--email-to',
        help='To email address'
    )
    
    # Slack configuration
    parser.add_argument(
        '--slack-webhook',
        help='Slack webhook URL'
    )
    
    # Other options
    parser.add_argument(
        '--version-file',
        help='Path to version tracking file (default: sonatype_last_version.txt)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without sending notifications'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load and validate configuration
    try:
        config = Config(args)
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no notifications will be sent")
        config.validate()
    except ConfigError as e:
        logger.error(str(e))
        logger.error("\nPlease provide configuration via:")
        logger.error("  1. Command-line arguments (see --help)")
        logger.error("  2. Environment variables")
        logger.error("  3. .env file (requires: pip install python-dotenv)")
        sys.exit(1)
    
    # Get latest version
    latest_version = get_latest_version()
    if not latest_version:
        logger.error("Failed to retrieve version information")
        sys.exit(1)
    
    # Check if version has changed
    last_version = read_last_version(config.version_file)
    
    if last_version is None:
        logger.info(f"First run - recording current version: {latest_version}")
        write_last_version(latest_version, config.version_file)
        sys.exit(0)
    
    if last_version != latest_version:
        logger.info(f"Version changed: {last_version} -> {latest_version}")
        
        if notify_new_version(config, latest_version):
            logger.info("Notifications sent successfully")
            write_last_version(latest_version, config.version_file)
            sys.exit(0)
        else:
            logger.error("All notification attempts failed")
            sys.exit(1)
    else:
        logger.info(f"No new version detected. Current version: {latest_version}")
        sys.exit(0)


if __name__ == '__main__':
    main()