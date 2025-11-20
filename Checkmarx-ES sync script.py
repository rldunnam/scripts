#!/usr/bin/env python3
"""
Sync Checkmarx SAST team memberships to Elasticsearch role mappings.

Sample Usage
# Simple - uses config variables
python sync_script.py

# Sync specific teams only
python sync_script.py --teams IT Engineering QA

# Dry run to preview changes
python sync_script.py --dry-run

# Create ES roles automatically if missing
python sync_script.py --create-roles

# Override a config value if needed
python sync_script.py --cx-password different_password --teams DIT
"""

import requests
import json
from typing import Dict, List, Set
from collections import defaultdict
import argparse
import logging

# ============================================================================
# CONFIGURATION - Update these values for your environment
# ============================================================================

# Checkmarx Configuration
CHECKMARX_URL = "https://checkmarx.example.com"
CHECKMARX_USERNAME = "admin"
CHECKMARX_PASSWORD = "your_password_here"

# Elasticsearch Configuration
ELASTICSEARCH_URL = "https://elasticsearch.example.com:9200"
ELASTICSEARCH_USERNAME = "elastic"
ELASTICSEARCH_PASSWORD = "your_password_here"

# ============================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CheckmarxClient:
    """Client for interacting with Checkmarx SAST API."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()
    
    def authenticate(self):
        """Authenticate and obtain access token."""
        auth_url = f"{self.base_url}/cxrestapi/auth/identity/connect/token"
        
        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password',
            'scope': 'sast_rest_api',
            'client_id': 'resource_owner_client',
            'client_secret': '014DF517-39D1-4453-B7B3-9930C563627C'
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = self.session.post(auth_url, data=data, headers=headers)
            response.raise_for_status()
            self.token = response.json()['access_token']
            self.session.headers.update({'Authorization': f'Bearer {self.token}'})
            logger.info("Successfully authenticated to Checkmarx")
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def get_teams(self) -> List[Dict]:
        """Get all teams from Checkmarx."""
        url = f"{self.base_url}/cxrestapi/auth/teams"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            teams = response.json()
            logger.info(f"Retrieved {len(teams)} teams from Checkmarx")
            return teams
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get teams: {e}")
            raise
    
    def get_users_by_team(self, team_id: int, team_name: str = "") -> List[Dict]:
        """Get all users for a specific team."""
        url = f"{self.base_url}/cxrestapi/auth/teams/{team_id}/users"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            users = response.json()
            return users
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"Access denied to team {team_id} ({team_name}). Skipping - user may not have permission.")
            else:
                logger.error(f"Failed to get users for team {team_id} ({team_name}): {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get users for team {team_id} ({team_name}): {e}")
            return []
    
    def get_team_memberships(self) -> Dict[str, Set[str]]:
        """
        Get team memberships mapping.
        Returns: Dict mapping team names to sets of usernames.
        """
        memberships = defaultdict(set)
        skipped_teams = []
        
        teams = self.get_teams()
        
        for team in teams:
            team_name = team['fullName']
            team_id = team['id']
            
            users = self.get_users_by_team(team_id, team_name)
            
            if users:
                for user in users:
                    username = user.get('userName', user.get('username', ''))
                    if username:
                        memberships[team_name].add(username)
                
                logger.info(f"Team '{team_name}': {len(users)} users")
            else:
                # Check if this was due to permission issue vs empty team
                skipped_teams.append(team_name)
        
        if skipped_teams:
            logger.warning(f"\nSkipped {len(skipped_teams)} team(s) due to permissions or no users")
        
        return dict(memberships)


class ElasticsearchClient:
    """Client for interacting with Elasticsearch Security API."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def get_role_mapping(self, role_name: str) -> Dict:
        """Get current role mapping for a role."""
        url = f"{self.base_url}/_security/role_mapping/{role_name}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json().get(role_name, {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get role mapping for {role_name}: {e}")
            return None
    
    def update_role_mapping(self, role_name: str, usernames: List[str], 
                          enabled: bool = True) -> bool:
        """
        Update role mapping with list of usernames.
        """
        url = f"{self.base_url}/_security/role_mapping/{role_name}"
        
        # Build the role mapping structure
        mapping = {
            "enabled": enabled,
            "roles": [role_name],
            "rules": {
                "any": [
                    {"field": {"username": username}} 
                    for username in usernames
                ]
            }
        }
        
        try:
            response = self.session.put(url, json=mapping)
            response.raise_for_status()
            logger.info(f"Updated role mapping '{role_name}' with {len(usernames)} users")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update role mapping {role_name}: {e}")
            return False
    
    def create_role_if_not_exists(self, role_name: str) -> bool:
        """Create a basic role if it doesn't exist."""
        url = f"{self.base_url}/_security/role/{role_name}"
        
        # Check if role exists
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                logger.info(f"Role '{role_name}' already exists")
                return True
        except:
            pass
        
        # Create basic role with minimal permissions
        role_def = {
            "cluster": ["monitor"],
            "indices": [
                {
                    "names": [f"{role_name.lower()}-*"],
                    "privileges": ["read", "view_index_metadata"]
                }
            ]
        }
        
        try:
            response = self.session.put(url, json=role_def)
            response.raise_for_status()
            logger.info(f"Created role '{role_name}'")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create role {role_name}: {e}")
            return False


def sync_team_memberships(cx_client: CheckmarxClient, 
                         es_client: ElasticsearchClient,
                         team_filter: List[str] = None,
                         create_roles: bool = False):
    """
    Sync Checkmarx team memberships to Elasticsearch role mappings.
    
    Args:
        cx_client: Checkmarx client instance
        es_client: Elasticsearch client instance
        team_filter: Optional list of team names to sync (sync all if None)
        create_roles: If True, create ES roles that don't exist
    """
    logger.info("Starting team membership sync")
    
    # Get team memberships from Checkmarx
    memberships = cx_client.get_team_memberships()
    
    # Filter teams if specified
    if team_filter:
        memberships = {k: v for k, v in memberships.items() if k in team_filter}
    
    # Sync each team to Elasticsearch
    success_count = 0
    fail_count = 0
    
    for team_name, usernames in memberships.items():
        logger.info(f"\nProcessing team: {team_name}")
        
        # Optionally create role if it doesn't exist
        if create_roles:
            es_client.create_role_if_not_exists(team_name)
        
        # Update role mapping
        if usernames:
            if es_client.update_role_mapping(team_name, list(usernames)):
                success_count += 1
            else:
                fail_count += 1
        else:
            logger.warning(f"Team '{team_name}' has no users, skipping")
    
    logger.info(f"\nSync complete: {success_count} successful, {fail_count} failed")


def main():
    parser = argparse.ArgumentParser(
        description='Sync Checkmarx SAST team memberships to Elasticsearch role mappings'
    )
    
    # Checkmarx arguments (optional - use config variables if not provided)
    parser.add_argument('--cx-url', default=CHECKMARX_URL, help='Checkmarx base URL')
    parser.add_argument('--cx-user', default=CHECKMARX_USERNAME, help='Checkmarx username')
    parser.add_argument('--cx-password', default=CHECKMARX_PASSWORD, help='Checkmarx password')
    
    # Elasticsearch arguments (optional - use config variables if not provided)
    parser.add_argument('--es-url', default=ELASTICSEARCH_URL, help='Elasticsearch base URL')
    parser.add_argument('--es-user', default=ELASTICSEARCH_USERNAME, help='Elasticsearch username')
    parser.add_argument('--es-password', default=ELASTICSEARCH_PASSWORD, help='Elasticsearch password')
    
    # Optional arguments
    parser.add_argument('--teams', nargs='+', help='Specific teams to sync (default: all)')
    parser.add_argument('--create-roles', action='store_true', 
                       help='Create ES roles if they don\'t exist')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be synced without making changes')
    parser.add_argument('--skip-empty', action='store_true',
                       help='Skip teams with no accessible users')
    
    args = parser.parse_args()
    
    try:
        # Initialize clients
        cx_client = CheckmarxClient(args.cx_url, args.cx_user, args.cx_password)
        cx_client.authenticate()
        
        es_client = ElasticsearchClient(args.es_url, args.es_user, args.es_password)
        
        # Perform sync
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            memberships = cx_client.get_team_memberships()
            if args.teams:
                memberships = {k: v for k, v in memberships.items() if k in args.teams}
            
            for team, users in memberships.items():
                print(f"\nTeam: {team}")
                print(f"Users ({len(users)}): {', '.join(sorted(users))}")
        else:
            sync_team_memberships(cx_client, es_client, args.teams, args.create_roles)
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
