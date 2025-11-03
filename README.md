# Butler Agent

Conversational Kubernetes cluster management. AI-powered local infrastructure assistant.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Overview

Manage Kubernetes in Docker (KinD) clusters using natural language. Create, start, stop, restart, and monitor local development environments without memorizing complex commands.

```bash
butler -p "create a cluster called dev"
# ✅ Cluster created in ~17s

butler -p "stop dev"
# ✅ Cluster stopped, data preserved

butler -p "start dev"
# ✅ Cluster started in ~5s
```

**[📖 Full Usage Guide](USAGE.md)** | **[🚀 Quick Start](#quick-setup)**

## Features

### ✨ Cluster Lifecycle Management
- **Create**: Launch clusters with built-in templates or custom configurations
- **Start/Stop**: Pause and resume clusters with state preservation (~5s startup)
- **Restart**: Quick reset for development iteration
- **Delete**: Clean removal of clusters and resources
- **Status**: Health checks, node status, and resource monitoring

### 🎛️ Custom Configurations
- **File-based configs**: Define cluster architecture in `./data/infra/kind-*.yaml`
- **Version control**: Commit cluster configs alongside your code
- **Priority-based discovery**: Named configs → Default config → Built-in templates
- **Example configs**: Comprehensive examples included

### 🤖 AI-Powered Interface
- **Natural language**: No command memorization needed
- **Context-aware**: Understands intent from conversation
- **Preference learning**: Remembers your patterns
- **Conversation history**: Save and resume sessions

### ⌨️ Keyboard Shortcuts
- **Shell commands**: Execute system commands with `!` (e.g., `!docker ps`, `!kubectl get pods`)
- **Quick clear**: Press `ESC` to clear the prompt
- **Mixed workflows**: Combine AI conversations with direct shell access
- **No context switching**: Stay in Butler while checking system state

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

# Get help
butler --help
```

### Interactive Mode Features

In interactive mode, you can:

- **Ask questions**: "what clusters do I have?"
- **Manage clusters**: "create a cluster called dev"
- **Execute shell commands**: `!docker ps`, `!kubectl get nodes`, `!ls -la`
- **Clear prompt**: Press `ESC` to clear current input
- **Auto-saved sessions**: Exit and resume anytime with `butler --continue`
- **Switch sessions**: Use `/continue` to pick from saved sessions

**See [USAGE.md](USAGE.md) for comprehensive examples and [docs/keybindings.md](docs/keybindings.md) for keyboard shortcuts.**

## Configuration

Configure via `.env` file:

```bash
# Required
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-codex

# Optional
BUTLER_DATA_DIR=./data                    # Cluster configs and data
BUTLER_INFRA_DIR=./data/infra             # Custom KinD configs
BUTLER_DEFAULT_K8S_VERSION=v1.34.0        # Default K8s version
LOG_LEVEL=info                            # debug, info, warning, error
```

See [.env.example](.env.example) for complete configuration options.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality guidelines, and contribution workflow.

## License

Apache License 2.0 - See LICENSE file for details

## Acknowledgments

- Built with [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- Inspired by [OSDU Agent](https://github.com/danielscholl/ai-examples/tree/main/osdu-agent)
- Part of the OSDU Community ecosystem
