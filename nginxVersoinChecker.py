import requests
import os
from bs4 import BeautifulSoup
import re

NGINX_DOWNLOAD_PAGE = "https://nginx.org/en/download.html"
VERSION_FILE = "nginx_last_version.txt"
SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/T5B327YJ0/<YOUR-WEBHOOK-TOKEN>'

def get_latest_stable_version():
    response = requests.get(NGINX_DOWNLOAD_PAGE)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the "Stable version" heading
    stable_header = soup.find("h4", string="Stable version")
    if not stable_header:
        raise ValueError("Stable version heading not found.")

    # Find the first <a> tag after the heading that links to a .tar.gz file with version
    table = stable_header.find_next("table")
    if not table:
        raise ValueError("Could not find stable version table.")

    # Look for a link that matches the version pattern
    link = table.find("a", href=re.compile(r"nginx-(\d+\.\d+\.\d+)\.tar\.gz"))
    if not link:
        raise ValueError("Could not find version link in stable version table.")

    # Extract version from link text
    match = re.search(r"nginx-(\d+\.\d+\.\d+)", link.text)
    if not match:
        raise ValueError("Version pattern not found in link text.")

    return match.group(1)

def read_stored_version():
    if not os.path.exists(VERSION_FILE):
        return None
    with open(VERSION_FILE, "r") as f:
        return f.read().strip()

def write_stored_version(version):
    with open(VERSION_FILE, "w") as f:
        f.write(version)

def notify_console(version):
    print(f"[!] New stable NGINX version available: {version}")

def notify_slack(version):
    message = {
        "text": f":tada: A new **stable** NGINX version is available: *{version}*. Check it out here: {NGINX_DOWNLOAD_PAGE}"
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=message)
    if response.status_code != 200:
        print(f"[!] Slack notification failed: {response.status_code}, {response.text}")

def main():
    try:
        latest = get_latest_stable_version()
        stored = read_stored_version()

        if latest != stored:
            notify_console(latest)
            notify_slack(latest)
            write_stored_version(latest)
        else:
            print(f"[✓] No new version. Latest is still {latest}")

    except Exception as e:
        print(f"[✗] Error checking NGINX version: {e}")

if __name__ == "__main__":
    main()

