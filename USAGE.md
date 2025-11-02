# Butler Agent Usage Guide

Comprehensive guide for using Butler Agent to manage Kubernetes in Docker (KinD) clusters.

## Table of Contents

- [Getting Started](#getting-started)
- [Cluster Lifecycle Operations](#cluster-lifecycle-operations)
- [Custom Cluster Configurations](#custom-cluster-configurations)
- [Interactive Mode](#interactive-mode)
- [Single Query Mode](#single-query-mode)
- [Examples](#examples)

## Getting Started

### Basic Commands

```bash
# Interactive chat mode
butler

# Single query execution
butler -p "create a minimal cluster called dev"

# Check system dependencies
butler --check

# Show configuration
butler --config

# Get help
butler --help
```

### Interactive Mode Commands

```
/clear               # Clear screen and reset conversation context
/save <name>         # Save conversation
/load <name>         # Load saved conversation
/list                # List saved conversations
/delete <name>       # Delete conversation
help                 # Show help
exit                 # Exit butler
```

## Cluster Lifecycle Operations

### Create Cluster

Create a new KinD cluster with various configurations:

```bash
# Minimal cluster (1 control-plane node, fastest)
butler -p "create a minimal cluster called dev"

# Default cluster (1 control-plane + 1 worker)
butler -p "create a cluster called staging"

# Custom cluster (1 control-plane + 3 workers)
butler -p "create a custom cluster called prod"

# With specific Kubernetes version
butler -p "create a minimal cluster called test with k8s version v1.30.0"
```

### Stop Cluster

Stop a running cluster to save resources while preserving all state:

```bash
butler -p "stop the dev cluster"
butler -p "stop dev"  # Short form
```

**When to use stop:**
- Saving laptop battery during breaks
- Pausing development overnight
- Freeing CPU/memory temporarily
- Need to resume work quickly later

**What's preserved:**
- All pods and deployments
- Persistent data
- Cluster configuration
- Kubeconfig

### Start Cluster

Resume a stopped cluster quickly (~5 seconds):

```bash
butler -p "start the dev cluster"
butler -p "start dev"  # Short form
```

**Performance:**
- Startup time: ~5 seconds (vs ~15-30s for recreate)
- All state preserved
- Kubernetes API ready immediately

### Restart Cluster

Quick stop + start cycle for development iteration:

```bash
butler -p "restart the dev cluster"
butler -p "restart dev"  # Short form
```

**Use cases:**
- Applying configuration changes
- Clearing transient state
- Quick cluster reset
- Development iteration

### Delete Cluster

Permanently remove a cluster and free all resources:

```bash
butler -p "delete the dev cluster"
butler -p "delete dev"  # Short form
```

**Note:** Butler will ask for confirmation before deleting.

### List Clusters

View all available clusters:

```bash
butler -p "list all clusters"
butler -p "what clusters do I have?"
butler -p "show clusters"
```

### Check Cluster Status

Get detailed cluster information:

```bash
butler -p "status of dev cluster"
butler -p "check health of dev"
butler -p "how is dev doing?"
```

## Custom Cluster Configurations

Butler supports custom KinD configurations using YAML files. This allows you to version-control your cluster architecture alongside your code.

### Configuration Discovery Priority

1. **Named custom configs**: `./data/infra/kind-{config}.yaml`
2. **Default custom config**: `./data/infra/kind-config.yaml`
3. **Built-in templates**: minimal, default, custom (fallback)

### Setup Custom Configuration

#### 1. Create infrastructure directory (if not exists)

```bash
mkdir -p ./data/infra
```

#### 2. Create custom configuration file

**Option A: Default custom config** (`kind-config.yaml`)
```yaml
# ./data/infra/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}  # Placeholder - will be replaced with cluster name
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
        protocol: TCP
  - role: worker
  - role: worker
```

**Option B: Named custom config** (`kind-dev.yaml`, `kind-prod.yaml`, etc.)
```yaml
# ./data/infra/kind-dev.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: {name}
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "env=dev,ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
      - containerPort: 443
        hostPort: 8443
  - role: worker
    kubeadmConfigPatches:
      - |
        kind: JoinConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "env=dev,workload=true"
```

#### 3. Use custom configuration

```bash
# Using named config (kind-dev.yaml)
butler -p "create a cluster called myapp using dev configuration"

# Using default custom config (kind-config.yaml)
butler -p "create a default cluster called myapp"

# Falls back to built-in if no custom config exists
butler -p "create a minimal cluster called test"
```

### Example Configurations

See `./data/infra/kind-config.yaml.example` for a comprehensive example with:
- Port mappings for ingress
- Multiple worker nodes
- Node labels
- Networking options
- Feature gates

### Configuration Best Practices

1. **Version control**: Commit your `kind-*.yaml` files to git
2. **Naming convention**: Use descriptive names (dev, staging, prod, ci)
3. **Documentation**: Add comments explaining special configurations
4. **Port conflicts**: Avoid overlapping host ports across configs
5. **Resource limits**: Consider your machine's capacity when adding nodes

## Examples

### Daily Development Workflow

```bash
# Morning: Start your cluster
butler -p "start my dev cluster"

# Work throughout the day...

# Lunch break: Stop to save battery
butler -p "stop dev"

# After lunch: Resume work
butler -p "start dev"

# End of day: Stop cluster
butler -p "stop dev"
```

### Testing Different Configurations

```bash
# Create test cluster with custom config
butler -p "create a cluster called test using dev configuration"

# Check it works
butler -p "status of test"

# Clean up
butler -p "delete test"
```

### Multi-Environment Setup

```bash
# Create different environments
butler -p "create a cluster called dev using dev config"
butler -p "create a cluster called staging using prod config"

# List all
butler -p "list clusters"

# Stop unused environments
butler -p "stop staging"

# Resume when needed
butler -p "start staging"
```

### Quick Iteration

```bash
# Create cluster
butler -p "create a minimal cluster called quick-test"

# Make changes, test...

# Quick restart to reset state
butler -p "restart quick-test"

# Done testing
butler -p "delete quick-test"
```

### Resource Management

```bash
# Check what's running
butler -p "list clusters"

# Stop clusters you're not using
butler -p "stop staging"
butler -p "stop prod"

# Keep only active development cluster running
# (saves CPU, memory, and battery)
```

## Advanced Usage

### Direct Kind Commands

Butler is a wrapper around kind. You can always use kind directly:

```bash
# View clusters
kind get clusters

# Check Docker containers
docker ps --filter "label=io.x-k8s.kind.cluster"

# View all containers (including stopped)
docker ps -a --filter "label=io.x-k8s.kind.cluster"
```

### Kubeconfig Management

Each cluster's kubeconfig is stored in:
```
./data/{cluster-name}/kubeconfig
```

Use with kubectl:
```bash
export KUBECONFIG=./data/dev/kubeconfig
kubectl get nodes

# Or use context
kubectl get nodes --context kind-dev
```

### Troubleshooting

**Cluster won't start:**
```bash
# Check Docker is running
docker ps

# Check container status
docker ps -a --filter "name={cluster-name}"

# View container logs
docker logs {cluster-name}-control-plane

# Check Butler logs
butler -v -p "start {cluster-name}"  # Verbose output
```

**Configuration not found:**
```bash
# List files in infra directory
ls -la ./data/infra/

# Check file naming (must be kind-{name}.yaml)
# Check YAML syntax
kind create cluster --config ./data/infra/kind-dev.yaml --dry-run
```

**Port conflicts:**
```bash
# Check what's using ports
lsof -i :8080
lsof -i :8443

# Adjust ports in your custom config
```

## Tips and Tricks

1. **Fast iteration**: Use `restart` instead of `delete` + `create`
2. **Save resources**: Use `stop` when taking breaks
3. **Multiple environments**: Create named configs for different scenarios
4. **Version control**: Commit your custom configs to git
5. **Batch operations**: Use shell scripts to manage multiple clusters
6. **Monitoring**: Use `butler --check` to verify dependencies
7. **Context switching**: Butler manages kubectl contexts automatically

## Environment Variables

Key configuration options:

```bash
# Infrastructure directory for custom configs
BUTLER_INFRA_DIR=./data/infra

# Data directory for cluster files
BUTLER_DATA_DIR=./data

# Default Kubernetes version
BUTLER_DEFAULT_K8S_VERSION=v1.34.0

# Cluster name prefix
BUTLER_CLUSTER_PREFIX=butler-

# Logging
LOG_LEVEL=info  # debug, info, warning, error
```

See [.env.example](.env.example) for complete configuration options.
