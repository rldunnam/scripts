#!/usr/bin/env python3
"""
Check Sonatype IQ server download page for newest version and alert each time a new version is available
"""

import re
import sys
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Slack webhook URL (replace with your actual webhook URL)
SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/T5B327YJ0/<YOUR SLACK TOKEN>'
#test webhook call: curl -X POST -H "Content-type: application/json" -d "{\"text\":\"test\"}" (SLACK_WEBHOOK_URL)

# Email settings (configure these)
#SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 587
EMAIL_USERNAME = 'email'
EMAIL_PASSWORD = 'your_password'
EMAIL_FROM = '<FROM EMAIL>'
EMAIL_TO = '<TO EMAIL>'

# URL to monitor
URL = 'https://help.sonatype.com/en/iq-server-release-notes.html'

VERSION_PATTERN = r"\b\d{3}\b"
VERSION_FILE = 'sonatype_last_version.txt'

def get_mocked_html():
    return """
    <html>
        <body>
            <h2>IQ Server CLI Version 191</h2>
            <p>Previous versions: 190, 189</p>
        </body>
    </html>
    """

def get_latest_version():
    try:
        response = requests.get(URL)
        response.raise_for_status()
        soup_html = response.text
        #soup_html = get_mocked_html()

        matches = re.findall(VERSION_PATTERN, soup_html)
        if matches:
            #normalized = [v if v.count('.') == 2 else v + '.0' for v in matches]
            #latest_version = sorted(normalized, key=lambda s: list(map(int, s.split('.'))), reverse=True)[0]
            latest_version = str(max(map(int, matches)))
            return latest_version
        else:
            return None
    except Exception as e:
        print(f"Error fetching or parsing page: {e}")
        sys.exit(1)

def read_last_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def write_last_version(version):
    with open(VERSION_FILE, 'w') as f:
        f.write(version)

def send_email_notification(version):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"New Sonatype IQ Server Version Detected: {version}"
    body = f"A new version {version} of the Sonatype IQ Server CLI has been released. Check it at {URL}."
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("Email notification sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_slack_notification(version):
    payload = {
        "text": f":tada: New Sonatype IQ Server CLI version detected: *{version}*. Check it here: {URL}"
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            print("Slack notification sent.")
        else:
            print(f"Failed to send Slack notification: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")

def notify_new_version(latest_version):
    print(f"New version detected: {latest_version}")
    send_email_notification(latest_version)
    send_slack_notification(latest_version)

def main():
    latest_version = get_latest_version()
    if not latest_version:
        print("No version found in the content.")
        return

    last_version = read_last_version() or ""
    
    if last_version.strip() != latest_version.strip():
        notify_new_version(latest_version)
        write_last_version(latest_version.strip())
    else:
        print(f"No new version. Latest is still {latest_version.strip()}.")

if __name__ == '__main__':
    main()

# Test cases
assert re.findall(r"\d+\.\d+(?:\.\d+)?", "Version 1.2.3") == ["1.2.3"]
assert re.findall(r"\d+\.\d+(?:\.\d+)?", "release 1.190.0-01") == ["1.190.0"]
assert re.findall(r"\d+\.\d+(?:\.\d+)?", "Latest version is 1.191") == ["1.191"]
assert sorted(["1.2.10", "1.2.2", "1.3.0"], key=lambda s: list(map(int, s.split('.'))), reverse=True)[0] == "1.3.0"
assert sorted(["1.191.0", "1.190.0", "1.189.0"], key=lambda s: list(map(int, s.split('.'))), reverse=True)[0] == "1.191.0"
print("All tests passed.")

