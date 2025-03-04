#!/usr/bin/env python3
"""
Utility functions for JFrog Artifactory Analyzer.
"""

import os
import json
import yaml
from typing import Dict, List, Any, Optional
from rich.console import Console

console = Console()

def load_config_file(file_path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] Config file not found: {file_path}")
        raise FileNotFoundError(f"Config file not found: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                return yaml.safe_load(f)
            elif file_path.endswith('.json'):
                return json.load(f)
            else:
                console.print(f"[bold red]Error:[/bold red] Unsupported config file format: {file_path}")
                raise ValueError(f"Unsupported config file format: {file_path}")
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        console.print(f"[bold red]Error:[/bold red] Failed to parse config file: {e}")
        raise

def save_results_to_file(results: Dict[str, Any], file_path: str) -> None:
    """Save analysis results to JSON file."""
    try:
        with open(file_path, 'w') as f:
            json.dump(results, f, indent=2)
        console.print(f"[green]Results saved to:[/green] {file_path}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to save results: {e}")
        raise

def format_repository_path(instance_name: str, repo_key: str) -> str:
    """Format a repository path for display."""
    return f"{instance_name}/{repo_key}"

def extract_repo_from_url(url: str, base_url: str) -> Optional[str]:
    """Extract repository key from a remote repository URL."""
    if not url.startswith(base_url):
        return None
    
    path = url[len(base_url):].strip('/')
    parts = path.split('/')
    
    # Handle various URL patterns
    # Example: https://artifactory.example.com/artifactory/repo-key
    if 'artifactory' in parts:
        artifactory_index = parts.index('artifactory')
        if len(parts) > artifactory_index + 1:
            return parts[artifactory_index + 1]
    # Example: https://artifactory.example.com/repo-key
    elif len(parts) > 0:
        return parts[0]
    
    return None

def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate the configuration file and return a list of errors, if any."""
    errors = []
    
    # Check if artifactory_instances exists and is a list
    if 'artifactory_instances' not in config:
        errors.append("Missing 'artifactory_instances' section in config")
        return errors
    
    if not isinstance(config['artifactory_instances'], list):
        errors.append("'artifactory_instances' must be a list")
        return errors
    
    # Check each instance
    for i, instance in enumerate(config['artifactory_instances']):
        instance_num = i + 1
        
        # Check required fields
        if 'name' not in instance:
            errors.append(f"Instance #{instance_num} is missing 'name' field")
        
        if 'url' not in instance:
            errors.append(f"Instance #{instance_num} is missing 'url' field")
        
        # Check authentication
        if 'api_key' not in instance and ('username' not in instance or 'password' not in instance):
            errors.append(f"Instance #{instance_num} ({instance.get('name', 'unnamed')}) is missing authentication details (either api_key or username/password)")
    
    return errors

def get_edge_label(edge_type: str) -> str:
    """Get a human-readable label for an edge type."""
    labels = {
        'remote': 'points to',
        'includes': 'includes',
        'deploys_to': 'deploys to',
        'depends_on': 'depends on'
    }
    return labels.get(edge_type, edge_type)

def redact_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a copy of the config with sensitive information redacted."""
    import copy
    
    # Deep copy to avoid modifying the original
    redacted_config = copy.deepcopy(config)
    
    # Redact sensitive information
    if 'artifactory_instances' in redacted_config:
        for instance in redacted_config['artifactory_instances']:
            if 'api_key' in instance:
                instance['api_key'] = '********'
            if 'password' in instance:
                instance['password'] = '********'
    
    return redacted_config