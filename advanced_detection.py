#!/usr/bin/env python3
"""
Advanced detection module for JFrog Artifactory Analyzer.

This module includes more sophisticated repository loop detection algorithms
and specialized detection for specific issue patterns.
"""

import networkx as nx
from typing import Dict, List, Set, Tuple, Any

class AdvancedDetection:
    """Advanced detection algorithms for JFrog repositories."""
    
    @staticmethod
    def find_include_cycles(graph: nx.DiGraph) -> List[List[str]]:
        """Find cycles involving only 'includes' relationships between virtual repositories."""
        include_graph = nx.DiGraph()
        
        # Create a subgraph with only 'includes' edges
        for u, v, data in graph.edges(data=True):
            if data.get('edge_type') == 'includes':
                include_graph.add_edge(u, v)
        
        # Find cycles in the include-only graph
        include_cycles = list(nx.simple_cycles(include_graph))
        return include_cycles
    
    @staticmethod
    def find_remote_chains(graph: nx.DiGraph) -> List[List[str]]:
        """Find chains of remote repositories that point to each other."""
        remote_graph = nx.DiGraph()
        
        # Create a subgraph with only 'remote' edges
        for u, v, data in graph.edges(data=True):
            if data.get('edge_type') == 'remote':
                remote_graph.add_edge(u, v)
        
        # Find all paths of length > 1 that could form a chain
        remote_chains = []
        for node in remote_graph.nodes():
            if remote_graph.out_degree(node) > 0:
                # Find all simple paths from this node to any other node
                for target in remote_graph.nodes():
                    if node != target:
                        for path in nx.all_simple_paths(remote_graph, node, target, cutoff=10):
                            if len(path) > 1:
                                remote_chains.append(path)
        
        return remote_chains
    
    @staticmethod
    def find_cross_instance_loops(graph: nx.DiGraph) -> List[List[str]]:
        """Find loops that span multiple Artifactory instances."""
        cross_instance_loops = []
        
        # Get all cycles
        all_cycles = list(nx.simple_cycles(graph))
        
        # Check each cycle to see if it spans multiple instances
        for cycle in all_cycles:
            instances = set()
            for node in cycle:
                instance = node.split(':')[0]  # Extract instance name from node ID
                instances.add(instance)
            
            # If cycle spans multiple instances, add it to the result
            if len(instances) > 1:
                cross_instance_loops.append(cycle)
        
        return cross_instance_loops
    
    @staticmethod
    def detect_repository_shadowing(graph: nx.DiGraph) -> List[Tuple[str, str]]:
        """
        Detect cases where multiple repositories with the same name exist across instances,
        which could lead to confusion or unintended behavior.
        """
        shadowed_repos = []
        repo_map = {}  # Maps repository names to their full node IDs
        
        # Group repositories by their key name
        for node in graph.nodes():
            repo_key = node.split(':')[-1]  # Extract repo name from node ID
            if repo_key not in repo_map:
                repo_map[repo_key] = []
            repo_map[repo_key].append(node)
        
        # Find repos with the same name across different instances
        for repo_key, nodes in repo_map.items():
            if len(nodes) > 1:
                # Check if they're on different instances
                instances = set(node.split(':')[0] for node in nodes)
                if len(instances) > 1:
                    # Add all pairs of shadowed repos
                    for i in range(len(nodes)):
                        for j in range(i+1, len(nodes)):
                            shadowed_repos.append((nodes[i], nodes[j]))
        
        return shadowed_repos
    
    @staticmethod
    def detect_long_dependency_chains(graph: nx.DiGraph, max_length: int = 5) -> List[List[str]]:
        """
        Detect long dependency chains that might cause performance issues.
        A long chain is defined as a path where repositories depend on each other in sequence.
        """
        long_chains = []
        
        # Find all simple paths of length greater than max_length
        for source in graph.nodes():
            for target in graph.nodes():
                if source != target:
                    for path in nx.all_simple_paths(graph, source, target, cutoff=max_length+1):
                        if len(path) > max_length:
                            long_chains.append(path)
        
        return long_chains
    
    @staticmethod
    def detect_isolated_repositories(graph: nx.DiGraph) -> List[str]:
        """
        Detect repositories that are not included in any virtual repository
        and are not used as a remote source, i.e., they are isolated.
        """
        isolated = []
        
        for node in graph.nodes():
            # Check if this node has any incoming edges
            if graph.in_degree(node) == 0:
                node_data = graph.nodes[node]
                # Only consider local repositories as potentially isolated
                if node_data.get('repo_type') == 'local':
                    isolated.append(node)
        
        return isolated
    
    @staticmethod
    def detect_all_issues(graph: nx.DiGraph) -> Dict[str, Any]:
        """Run all detection algorithms and return a comprehensive report."""
        results = {
            'include_cycles': AdvancedDetection.find_include_cycles(graph),
            'remote_chains': AdvancedDetection.find_remote_chains(graph),
            'cross_instance_loops': AdvancedDetection.find_cross_instance_loops(graph),
            'shadowed_repositories': AdvancedDetection.detect_repository_shadowing(graph),
            'long_dependency_chains': AdvancedDetection.detect_long_dependency_chains(graph),
            'isolated_repositories': AdvancedDetection.detect_isolated_repositories(graph)
        }
        
        return results