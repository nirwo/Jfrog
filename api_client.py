#!/usr/bin/env python3
"""
API client for JFrog Artifactory for retrieving repository information.
"""

import requests
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin

logger = logging.getLogger("jfrog-analyser")

class ArtifactoryApiClient:
    """Client for interacting with JFrog Artifactory API."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, 
                 username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize API client with authentication details.
        
        Args:
            base_url: Base URL of Artifactory instance (e.g., https://artifactory.example.com/artifactory)
            api_key: API key for authentication (preferred)
            username: Username for basic authentication
            password: Password for basic authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.username = username
        self.password = password
        
        # Verify that we have some form of authentication
        if not api_key and not (username and password):
            logger.warning("No authentication provided for Artifactory API client")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get the appropriate authentication headers."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.api_key:
            headers['X-JFrog-Art-Api'] = self.api_key
        elif self.username and self.password:
            import base64
            auth_str = f"{self.username}:{self.password}"
            headers['Authorization'] = f"Basic {base64.b64encode(auth_str.encode()).decode()}"
        
        return headers
    
    def get_repositories(self) -> List[Dict[str, Any]]:
        """
        Get a list of all repositories.
        
        Returns:
            List of repository data
        """
        url = f"{self.base_url}/api/repositories"
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get repositories: {e}")
            return []
    
    def get_repository_details(self, repo_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific repository.
        
        Args:
            repo_key: Repository key/name
            
        Returns:
            Repository details or None if not found
        """
        url = f"{self.base_url}/api/repositories/{repo_key}"
        try:
            response = requests.get(url, headers=self.get_auth_headers())
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get repository details for {repo_key}: {e}")
            return None
    
    def get_all_repository_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all repositories.
        
        Returns:
            Dictionary mapping repository keys to their details
        """
        repos = {}
        basic_repos = self.get_repositories()
        
        for repo in basic_repos:
            repo_key = repo['key']
            details = self.get_repository_details(repo_key)
            if details:
                repos[repo_key] = details
            else:
                # Fall back to basic info if detailed info not available
                repos[repo_key] = repo
        
        return repos
    
    def get_remote_repository_target(self, repo_key: str) -> Optional[Tuple[str, str]]:
        """
        Get the target URL and repository key for a remote repository.
        
        Args:
            repo_key: Repository key/name
            
        Returns:
            Tuple of (target_url, target_repo_key) or None if not a remote repository
            or if the target can't be determined
        """
        details = self.get_repository_details(repo_key)
        if not details or details.get('type') != 'remote':
            return None
        
        remote_url = details.get('url')
        if not remote_url:
            return None
        
        # Attempt to extract target repository key from URL
        # This is a simplistic approach and may need refinement for specific use cases
        try:
            # Common patterns for Artifactory URLs
            # https://artifactory.example.com/artifactory/repo-key
            if '/artifactory/' in remote_url:
                repo_part = remote_url.split('/artifactory/', 1)[1].strip('/')
                parts = repo_part.split('/')
                target_repo = parts[0] if parts else None
                return (remote_url, target_repo)
            else:
                # Try to extract the last part of the URL as the repo name
                from urllib.parse import urlparse
                path = urlparse(remote_url).path.strip('/')
                parts = path.split('/')
                target_repo = parts[-1] if parts else None
                return (remote_url, target_repo)
        except Exception as e:
            logger.error(f"Failed to extract target repo from URL {remote_url}: {e}")
            return (remote_url, None)
    
    def get_virtual_repository_includes(self, repo_key: str) -> List[str]:
        """
        Get the list of repositories included in a virtual repository.
        
        Args:
            repo_key: Repository key/name
            
        Returns:
            List of repository keys included in the virtual repository
        """
        details = self.get_repository_details(repo_key)
        if not details or details.get('type') != 'virtual':
            return []
        
        return details.get('repositories', [])
    
    def get_repository_type(self, repo_key: str) -> Optional[str]:
        """
        Get the type of a repository (local, remote, virtual, etc.).
        
        Args:
            repo_key: Repository key/name
            
        Returns:
            Repository type or None if not found
        """
        details = self.get_repository_details(repo_key)
        if not details:
            return None
        
        return details.get('type')
    
    def test_connection(self) -> bool:
        """
        Test the connection to the Artifactory instance.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/system/ping", 
                headers=self.get_auth_headers()
            )
            return response.status_code == 200
        except requests.RequestException:
            return False