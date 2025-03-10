# JFrog Artifactory Analyzer

A tool to analyze JFrog Artifactory configurations and detect potential repository loops across multiple Artifactory nodes.

## Overview

When managing multiple Artifactory instances, it's possible to create repository loops that can cause performance issues or infinite recursion. This tool helps identify such loops.

Common loop scenarios include:
- Remote repository pointing to a virtual repository instead of a remote/local repository
- Circular dependencies between virtual repositories
- Chains of remote repositories that eventually point back to the original source
- Multiple virtual repositories including each other in a circular pattern

## Features

- Detect repository loops across multiple Artifactory instances
- Identify remote repositories pointing to virtual repositories (anti-pattern)
- Find cross-instance dependencies that may cause circular references
- Visualize repository relationships with color-coded graph
- Generate comprehensive reports of potential issues
- Provide recommendations for resolving detected loops

## Requirements

- Python 3.8+
- Access to JFrog Artifactory API
- Required Python packages:
  - requests
  - networkx
  - matplotlib
  - pyyaml
  - rich

## Installation

```bash
git clone https://github.com/your-username/jfrog-analyser.git
cd jfrog-analyser
pip install -r requirements.txt
```

## Usage

1. Create a configuration file (see below)
2. Run the analyzer:

```bash
python jfrog_analyser.py --config config.yaml
```

Additional options:
```bash
# Enable verbose logging
python jfrog_analyser.py --config config.yaml --verbose

# Save results to a file
python jfrog_analyser.py --config config.yaml --output results.json

# Generate only the visualization
python jfrog_analyser.py --config config.yaml --visualize-only
```

## Configuration

Create a `config.yaml` file with your Artifactory instances (see `sample_config.yaml` for a complete example):

```yaml
artifactory_instances:
  - name: artifactory1
    url: https://artifactory1.example.com/artifactory
    api_key: your_api_key_here
  
  - name: artifactory2
    url: https://artifactory2.example.com/artifactory
    api_key: your_api_key_here
```

You can also use username/password authentication:

```yaml
artifactory_instances:
  - name: artifactory1
    url: https://artifactory1.example.com/artifactory
    username: admin
    password: password
```

## Advanced Detection

The tool includes advanced detection capabilities:

1. **Repository Loops**: Detects circular dependencies between repositories
2. **Remote to Virtual Issues**: Identifies remote repositories pointing to virtual repositories
3. **Cross-Instance Loops**: Finds loops that span multiple Artifactory instances
4. **Repository Shadowing**: Detects repositories with the same name across instances
5. **Long Dependency Chains**: Identifies excessively long dependency chains
6. **Isolated Repositories**: Finds local repositories not included in any virtual repository

## Visualization

The tool generates a visualization of repository relationships:
- Green nodes: Local repositories
- Blue nodes: Remote repositories
- Red nodes: Virtual repositories
- Blue edges: Remote relationships
- Red edges: Include relationships

## Example Report

Here's an example of what the report looks like:

```
                          JFrog Artifactory Analysis Report                          

                 Detected Repository Loops (2)                 
33
 Loop #  Loop Path                                            Repository Types      
!GG)
 1      art1:maven-virtual � art1:maven-remote � art1:maven-virtual  virtual, remote, virtual 
 2      art2:npm-virt � art1:npm-virt � art2:npm-virt        virtual, virtual, virtual 
       4                                                       4                         


    Remote Repositories Pointing to Virtual Repositories (1)     
33
 Remote Repository     Virtual Repository    Recommendation                                        
!GG)
 art1/maven-remote     art1/maven-virtual    Point to a specific local or remote repository instead of the virtual repository 
                     4                     4                                                      
```

## License

MIT