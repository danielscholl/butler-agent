# Butler Agent

Conversational Kubernetes cluster management. AI-powered local infrastructure assistant.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Overview

Manage Kubernetes in Docker (KinD) clusters using natural language. Create, configure, and monitor local development environments without memorizing complex commands.

```bash
# Start interactive chat
butler

 ☸  Welcome to Butler

Butler manages Kubernetes clusters locally with natural language.
Butler uses AI - always verify operations before executing.

 ~/butler-agent [⎇ main]                                   gpt-5-codex · v0.1.0
────────────────────────────────────────────────────────────────────────────────
> create a cluster called dev
☸ Complete (3.2s) - msg:1 tool:1

☸ Cluster 'dev' created successfully with 2 nodes
  • Kubeconfig: ./data/dev/kubeconfig
  • Nodes: 1 control-plane, 1 worker

────────────────────────────────────────────────────────────────────────────────
> what clusters do I have?
☸ Complete (1.5s) - msg:2 tool:1

You have 1 cluster: dev (running, 2/2 nodes ready)
```

Supports cluster lifecycle, health checks, and configuration management. Includes conversation persistence and preference learning.

## Prerequisites

### Azure Resources (Cloud)

**Required:**
- [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource) deployment with a model (e.g., gpt-5-codex, gpt-4)

**Optional (for observability):**
- [Azure Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview) for telemetry

### Local Tools (Client)

**Required:**
- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Docker (running)

**Optional:**
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) - auth via `az login`
- kubectl - for direct cluster access
- kind - automatically verified by `butler --check`

## Quick Setup

```bash
# Install from source
uv tool install git+https://github.com/danielscholl/butler-agent.git

# Configure required credentials
cp .env.example .env
```

**Authenticate with CLI tools** (recommended):
```bash
az login      # For Azure OpenAI
```

**OR use API keys** (if CLI not available):
```bash
# Edit .env file:
# AZURE_OPENAI_API_KEY=your-key
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-codex
```

**Verify setup**:
```bash
butler --check    # Check dependencies and configuration
butler --config   # Show current configuration
```

## Usage

```bash
# Interactive chat mode
butler

# Single query
butler -p "create a minimal cluster called test"

# Health check
butler --check

# Show configuration
butler --config

# Get help
butler --help
```

### Interactive Commands

```
/clear               # Clear screen and reset conversation context
/save <name>         # Save conversation
/load <name>         # Load saved conversation
/list                # List saved conversations
/delete <name>       # Delete conversation
help                 # Show help
exit                 # Exit butler
```

### Cluster Configurations

- **Minimal** (1 node): `"create a minimal cluster"`
- **Default** (2 nodes): `"create a cluster"` - includes port forwarding 80/443
- **Custom** (4 nodes): `"create a custom cluster"` - simulates production

## Configuration

Key environment variables:

```bash
# LLM Provider (required)
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-codex

# Agent Settings (optional)
BUTLER_DATA_DIR=./data                                # Cluster configs
BUTLER_DEFAULT_K8S_VERSION=v1.34.0                    # K8s version
LOG_LEVEL=info                                        # Logging level
```

See [.env.example](.env.example) for all options.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality guidelines, and contribution workflow.

## License

Apache License 2.0 - See LICENSE file for details

## Acknowledgments

- Built with [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- Inspired by [OSDU Agent](https://github.com/danielscholl/ai-examples/tree/main/osdu-agent)
- Part of the OSDU Community ecosystem
