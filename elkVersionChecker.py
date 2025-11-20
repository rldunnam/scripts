#!/usr/bin/env python3
"""
Check ELK download page for newest version and alert each time a new version is available
"""
import requests
from bs4 import BeautifulSoup
import re
import os

# --- Config ---
DOWNLOADS_URL = "https://www.elastic.co/downloads/elasticsearch"
VERSION_FILE = "/tmp/elasticsearch_version_check.txt"  # Update path as needed
# Replace with your Slack webhook
SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/T5B327YJ0/<YOUR SLACK TOKEN>'

# --- Functions ---

def fetch_latest_version():
    response = requests.get(DOWNLOADS_URL)
    if response.status_code != 200:
        print(f"Failed to fetch download page: {response.status_code}")
        return None

    # Directly search the raw HTML for the version string
    match = re.search(r'Version:\s*</strong>\s*([\d\.]+)</p>', response.text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None

def read_stored_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def write_version(version):
    with open(VERSION_FILE, 'w') as f:
        f.write(version)

def send_slack_notification(version):
    message = {
        "text": f":tada: New Elasticsearch version available: *{version}*.  Check it out here: {DOWNLOADS_URL}"
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=message)
    if response.status_code != 200:
        print(f"Slack notification failed: {response.status_code} - {response.text}")
    else:
        print("Slack notification sent.")

def check_for_new_version():
    latest_version = fetch_latest_version()
    if not latest_version:
        print("Could not determine latest version.")
        return

    stored_version = read_stored_version()
    if stored_version != latest_version:
        print(f"New version detected: {latest_version} (previous: {stored_version})")
        write_version(latest_version)
        send_slack_notification(latest_version)
    else:
        print(f"No update. Current version is still: {stored_version}")

# --- Main ---
if __name__ == "__main__":
    check_for_new_version()

