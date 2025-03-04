#!/usr/bin/env python3
"""
JFrog Artifactory Repository Loop Analyzer

This tool analyzes JFrog Artifactory configurations to detect repository loops
across multiple Artifactory instances.
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Set, Tuple, Optional, Any

import yaml
import requests
import networkx as nx
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from dotenv import load_dotenv
import matplotlib.pyplot as plt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("jfrog-analyser")

# Rich console for pretty output
console = Console()

class ArtifactoryInstance:
    """Represents a JFrog Artifactory instance."""
    
    def __init__(self, name: str, url: str, api_key: str = None, username: str = None, password: str = None):
        self.name = name
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.username = username
        self.password = password
        self.repositories = {}
        
    def __str__(self) -> str:
        return f"{self.name} ({self.url})"
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if self.api_key:
            return {"X-JFrog-Art-Api": self.api_key}
        elif self.username and self.password:
            return {"Authorization": f"Basic {self.get_basic_auth()}"}
        return {}
    
    def get_basic_auth(self) -> str:
        """Generate Basic auth string."""
        import base64
        auth_str = f"{self.username}:{self.password}"
        return base64.b64encode(auth_str.encode()).decode()
    
    def fetch_repositories(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all repositories from this Artifactory instance."""
        try:
            headers = self.get_auth_headers()
            repos_url = f"{self.url}/api/repositories"
            
            response = requests.get(repos_url, headers=headers)
            response.raise_for_status()
            
            # Get basic repository information
            repos_list = response.json()
            
            # Fetch detailed info for each repository
            for repo in repos_list:
                repo_key = repo['key']
                repo_detail_url = f"{self.url}/api/repositories/{repo_key}"
                detail_response = requests.get(repo_detail_url, headers=headers)
                
                if detail_response.status_code == 200:
                    self.repositories[repo_key] = detail_response.json()
                else:
                    logger.warning(f"Failed to fetch details for repository {repo_key}")
                    self.repositories[repo_key] = repo
            
            logger.info(f"Fetched {len(self.repositories)} repositories from {self.name}")
            return self.repositories
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch repositories from {self.name}: {e}")
            return {}


class JFrogAnalyser:
    """Main class for analyzing JFrog Artifactory configurations."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.instances: List[ArtifactoryInstance] = []
        self.repository_graph = nx.DiGraph()
        self.detected_loops = []
        
        # Load configuration
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Process Artifactory instances
            for instance in config.get('artifactory_instances', []):
                name = instance.get('name')
                url = instance.get('url')
                api_key = instance.get('api_key')
                username = instance.get('username')
                password = instance.get('password')
                
                if not url:
                    logger.error(f"Missing URL for Artifactory instance {name}")
                    continue
                
                if not api_key and not (username and password):
                    logger.error(f"Missing authentication details for {name}")
                    continue
                
                self.instances.append(
                    ArtifactoryInstance(name, url, api_key, username, password)
                )
            
            logger.info(f"Loaded {len(self.instances)} Artifactory instances from config")
            
        except (yaml.YAMLError, FileNotFoundError) as e:
            logger.error(f"Failed to load config file: {e}")
            sys.exit(1)
    
    def fetch_all_repositories(self):
        """Fetch repositories from all configured Artifactory instances."""
        for instance in self.instances:
            instance.fetch_repositories()
    
    def build_repository_graph(self):
        """Build a directed graph of repository relationships."""
        # Clear existing graph
        self.repository_graph.clear()
        
        # Add nodes for all repositories
        for instance in self.instances:
            for repo_key, repo_data in instance.repositories.items():
                node_id = f"{instance.name}:{repo_key}"
                self.repository_graph.add_node(
                    node_id,
                    instance=instance.name,
                    repo_key=repo_key,
                    repo_type=repo_data.get('type', 'unknown'),
                    package_type=repo_data.get('packageType', 'unknown')
                )
        
        # Add edges for repository relationships
        for instance in self.instances:
            for repo_key, repo_data in instance.repositories.items():
                source_node = f"{instance.name}:{repo_key}"
                
                # For remote repositories, check URL to see if it points to another Artifactory
                if repo_data.get('type') == 'remote':
                    remote_url = repo_data.get('url', '')
                    
                    # Check if this remote URL points to one of our known instances
                    for target_instance in self.instances:
                        if remote_url.startswith(target_instance.url):
                            # Extract the repository key from the remote URL
                            # The format is usually: https://artifactory-url/artifactory/repo-key
                            url_path = remote_url[len(target_instance.url):].strip('/')
                            if url_path.startswith('api/'):
                                continue  # Skip API endpoints
                                
                            # Handle various URL formats
                            parts = url_path.split('/')
                            if len(parts) >= 1:
                                target_repo = parts[-1]  # Last part should be repo name
                                
                                # Verify this repository exists in the target instance
                                if target_repo in target_instance.repositories:
                                    target_node = f"{target_instance.name}:{target_repo}"
                                    self.repository_graph.add_edge(
                                        source_node, 
                                        target_node,
                                        edge_type='remote'
                                    )
                                    logger.debug(f"Added remote edge: {source_node} -> {target_node}")
                
                # For virtual repositories, check includes
                if repo_data.get('type') == 'virtual':
                    # Virtual repositories can include other repositories from the same instance
                    for included_repo in repo_data.get('repositories', []):
                        if included_repo in instance.repositories:
                            target_node = f"{instance.name}:{included_repo}"
                            self.repository_graph.add_edge(
                                source_node,
                                target_node,
                                edge_type='includes'
                            )
                            logger.debug(f"Added include edge: {source_node} -> {target_node}")
        
        logger.info(f"Built repository graph with {self.repository_graph.number_of_nodes()} nodes and {self.repository_graph.number_of_edges()} edges")
    
    def detect_loops(self):
        """Detect loops in the repository graph."""
        self.detected_loops = list(nx.simple_cycles(self.repository_graph))
        
        if self.detected_loops:
            logger.warning(f"Detected {len(self.detected_loops)} repository loops!")
            return self.detected_loops
        else:
            logger.info("No repository loops detected.")
            return []
    
    def detect_remote_to_virtual_issues(self):
        """Detect remote repositories pointing to virtual repositories."""
        issues = []
        
        for node, node_data in self.repository_graph.nodes(data=True):
            if node_data.get('repo_type') == 'remote':
                for successor in self.repository_graph.successors(node):
                    successor_data = self.repository_graph.nodes[successor]
                    if successor_data.get('repo_type') == 'virtual':
                        issues.append((node, successor))
                        logger.warning(f"Remote repository {node} points to virtual repository {successor}")
        
        return issues
    
    def generate_report(self):
        """Generate a report of detected issues."""
        console.rule("[bold red]JFrog Artifactory Analysis Report")
        
        # Report on repository loops
        if self.detected_loops:
            table = Table(title=f"Detected Repository Loops ({len(self.detected_loops)})")
            table.add_column("Loop #", style="dim")
            table.add_column("Loop Path", style="red")
            table.add_column("Repository Types", style="blue")
            
            for i, loop in enumerate(self.detected_loops, 1):
                path = " → ".join(loop + [loop[0]])  # Add first node again to show complete loop
                
                # Get repository types for each node in the loop
                repo_types = []
                for node in loop:
                    node_data = self.repository_graph.nodes[node]
                    repo_types.append(f"{node_data.get('repo_type', 'unknown')}")
                
                table.add_row(str(i), path, ", ".join(repo_types))
            
            console.print(table)
        else:
            console.print("[green]✓ No repository loops detected")
        
        # Report on remote-to-virtual issues
        remote_virtual_issues = self.detect_remote_to_virtual_issues()
        if remote_virtual_issues:
            console.print("\n")
            table = Table(title=f"Remote Repositories Pointing to Virtual Repositories ({len(remote_virtual_issues)})")
            table.add_column("Remote Repository", style="cyan")
            table.add_column("Virtual Repository", style="magenta")
            table.add_column("Recommendation", style="green")
            
            for remote, virtual in remote_virtual_issues:
                remote_parts = remote.split(":")
                virtual_parts = virtual.split(":")
                
                remote_name = f"{remote_parts[0]}/{remote_parts[1]}"
                virtual_name = f"{virtual_parts[0]}/{virtual_parts[1]}"
                
                recommendation = f"Point to a specific local or remote repository instead of the virtual repository"
                
                table.add_row(remote_name, virtual_name, recommendation)
            
            console.print(table)
    
    def visualize_graph(self, output_file: str = 'repository_graph.png'):
        """Visualize the repository graph."""
        try:
            plt.figure(figsize=(12, 10))
            
            # Create position layout
            pos = nx.spring_layout(self.repository_graph, seed=42)
            
            # Draw nodes with different colors based on type
            repo_types = nx.get_node_attributes(self.repository_graph, 'repo_type')
            
            local_repos = [node for node, data in self.repository_graph.nodes(data=True) 
                         if data.get('repo_type') == 'local']
            remote_repos = [node for node, data in self.repository_graph.nodes(data=True) 
                          if data.get('repo_type') == 'remote']
            virtual_repos = [node for node, data in self.repository_graph.nodes(data=True) 
                           if data.get('repo_type') == 'virtual']
            other_repos = [node for node, data in self.repository_graph.nodes(data=True) 
                         if data.get('repo_type') not in ['local', 'remote', 'virtual']]
            
            # Draw nodes
            nx.draw_networkx_nodes(self.repository_graph, pos, nodelist=local_repos, 
                                  node_color='green', node_size=500, alpha=0.8, label='Local')
            nx.draw_networkx_nodes(self.repository_graph, pos, nodelist=remote_repos, 
                                  node_color='blue', node_size=500, alpha=0.8, label='Remote')
            nx.draw_networkx_nodes(self.repository_graph, pos, nodelist=virtual_repos, 
                                  node_color='red', node_size=500, alpha=0.8, label='Virtual')
            nx.draw_networkx_nodes(self.repository_graph, pos, nodelist=other_repos, 
                                  node_color='gray', node_size=500, alpha=0.8, label='Other')
            
            # Draw edges with different styles based on type
            edge_types = nx.get_edge_attributes(self.repository_graph, 'edge_type')
            
            remote_edges = [(u, v) for u, v, data in self.repository_graph.edges(data=True) 
                           if data.get('edge_type') == 'remote']
            include_edges = [(u, v) for u, v, data in self.repository_graph.edges(data=True) 
                            if data.get('edge_type') == 'includes']
            other_edges = [(u, v) for u, v, data in self.repository_graph.edges(data=True) 
                          if data.get('edge_type') not in ['remote', 'includes']]
            
            # Draw edges
            nx.draw_networkx_edges(self.repository_graph, pos, edgelist=remote_edges, 
                                  width=1.5, alpha=0.7, edge_color='blue', 
                                  connectionstyle='arc3,rad=0.1', label='Remote')
            nx.draw_networkx_edges(self.repository_graph, pos, edgelist=include_edges, 
                                  width=1.5, alpha=0.7, edge_color='red', 
                                  connectionstyle='arc3,rad=0.1', label='Includes')
            nx.draw_networkx_edges(self.repository_graph, pos, edgelist=other_edges, 
                                  width=1.5, alpha=0.7, edge_color='gray', 
                                  connectionstyle='arc3,rad=0.1', label='Other')
            
            # Draw labels with shortened names
            labels = {}
            for node in self.repository_graph.nodes():
                labels[node] = node.split(':')[-1]  # Just show repo name, not instance
            
            nx.draw_networkx_labels(self.repository_graph, pos, labels, font_size=8)
            
            plt.title('JFrog Artifactory Repository Relationships')
            plt.legend(loc='upper right')
            plt.axis('off')
            plt.tight_layout()
            
            # Save the figure
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            logger.info(f"Graph visualization saved to {output_file}")
            
            # Close the plot to free resources
            plt.close()
            
        except Exception as e:
            logger.error(f"Failed to visualize graph: {e}")
    
    def analyze(self):
        """Run the full analysis workflow."""
        console.print("[bold blue]Starting JFrog Artifactory Analysis...[/bold blue]")
        
        # Fetch repositories
        with console.status("[bold green]Fetching repositories from Artifactory instances..."):
            self.fetch_all_repositories()
        
        # Build repository graph
        with console.status("[bold green]Building repository relationship graph..."):
            self.build_repository_graph()
        
        # Detect loops
        with console.status("[bold green]Detecting repository loops..."):
            self.detect_loops()
        
        # Generate report
        self.generate_report()
        
        # Visualize graph
        with console.status("[bold green]Visualizing repository relationships..."):
            self.visualize_graph()
        
        console.print("[bold blue]Analysis complete![/bold blue]")


def main():
    """Main entry point for the script."""
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='JFrog Artifactory Repository Loop Analyzer')
    parser.add_argument('--config', '-c', type=str, default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Run analysis
    analyser = JFrogAnalyser(args.config)
    analyser.analyze()


if __name__ == '__main__':
    main()