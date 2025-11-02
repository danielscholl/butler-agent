# Butler Agent

[![CI](https://github.com/OWNER/REPO/workflows/CI/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Security](https://github.com/OWNER/REPO/workflows/Security%20Scanning/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/OWNER/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/OWNER/REPO)

> AI-powered conversational DevOps agent for Kubernetes infrastructure management

Butler Agent provides a natural language interface for managing Kubernetes in Docker (KinD) clusters. Instead of memorizing complex commands, simply tell Butler what you want to do.

## Features

- **Conversational Interface**: Manage clusters using natural language with multi-turn conversation support
- **Conversation Persistence**: Save and resume conversations across sessions
- **Memory & Learning**: Agent learns your preferences and provides personalized suggestions
- **Multi-Provider LLM Support**: Works with OpenAI and Azure OpenAI
- **KinD Cluster Management**: Create, delete, list, and monitor local Kubernetes clusters
- **Rich Console Output**: Beautiful formatted output with tables, panels, and progress indicators
- **Intelligent Error Handling**: Context-aware error messages and troubleshooting suggestions
- **Observability**: Optional Azure Application Insights integration with execution metrics

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Docker (running)
- kubectl (recommended)
- kind (recommended)

### Installation

```bash
# Clone the repository
cd butler-agent

# Install with uv
uv sync

# Or install as a tool
uv tool install .
```

### Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Configure your LLM provider in `.env`:

**Option A: Azure OpenAI (default)**
```env
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

**Option B: OpenAI**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Basic Usage

**Interactive Mode:**
```bash
butler
```

**Single Query Mode:**
```bash
butler -p "create a cluster called dev-env"
butler -p "what clusters do I have?"
butler -p "show status for dev-env"
```

## Example Conversations

```
You: Create a cluster called dev-env
Butler: Creating KinD cluster "dev-env"...
        ✓ Cluster created successfully with 2 nodes
        • Kubeconfig: ./data/dev-env/kubeconfig
        Your cluster is ready!

You: What's the status?
Butler: Cluster 'dev-env' is running with 2/2 nodes ready

        ┌─────────────────────────────────┐
        │ Cluster Status: dev-env         │
        ├────────────┬────────────────────┤
        │ Property   │ Value              │
        ├────────────┼────────────────────┤
        │ Status     │ running            │
        │ Nodes      │ 2                  │
        │ Ready      │ 2                  │
        └────────────┴────────────────────┘

You: Delete dev-env
Butler: Are you sure you want to delete cluster 'dev-env'?
        This action cannot be undone. (yes/no)

You: yes
Butler: ✓ Cluster 'dev-env' deleted successfully
```

## Conversation Management

Butler now supports saving and resuming conversations, allowing you to maintain context across sessions:

```bash
# Save your current conversation
/save my-dev-setup

# List all saved conversations
/list

# Load a previous conversation
/load my-dev-setup

# Delete a saved conversation
/delete old-conversation

# Start a fresh conversation (reset context)
/new
```

Conversations are automatically saved to `~/.butler/conversations/` and include all context, preferences, and history.

## Memory & Learning

Butler learns from your interactions to provide a personalized experience:

- **Cluster Preferences**: Remembers your preferred cluster configurations (minimal, default, custom)
- **Naming Patterns**: Learns and suggests cluster naming patterns based on your history
- **Kubernetes Versions**: Remembers your preferred K8s versions
- **Usage Metrics**: Tracks session statistics and successful operations

The agent will provide smarter suggestions based on your past behavior!

## Cluster Configurations

Butler supports three cluster configurations:

### Minimal (1 node)
```bash
butler -p "create a minimal cluster called test"
```
- 1 control-plane node
- Fastest startup
- Minimal resource usage

### Default (2 nodes)
```bash
butler -p "create a cluster called dev"
```
- 1 control-plane node
- 1 worker node
- Port forwarding for HTTP/HTTPS (80, 443)
- Suitable for most development scenarios

### Custom (4 nodes)
```bash
butler -p "create a custom cluster called prod-sim"
```
- 1 control-plane node
- 3 worker nodes
- Port forwarding for HTTP/HTTPS
- Simulates production-like environment

## CLI Options

```
butler                    # Interactive chat mode
butler -p "query"         # Single query mode
butler -q                 # Quiet mode (minimal output)
butler -v                 # Verbose mode (debug logging)
butler --version          # Show version
```

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai, azure) | `azure` |
| `MODEL_NAME` | Override default model for provider | Provider-specific |
| `BUTLER_DATA_DIR` | Data directory for cluster configs | `./data` |
| `BUTLER_CLUSTER_PREFIX` | Prefix for cluster names | `butler-` |
| `BUTLER_DEFAULT_K8S_VERSION` | Default Kubernetes version | `v1.34.0` |
| `LOG_LEVEL` | Logging level (debug, info, warning, error) | `info` |

### Provider-Specific Variables

**OpenAI:**
- `OPENAI_API_KEY` (required)
- `OPENAI_BASE_URL` (optional)
- `OPENAI_ORGANIZATION` (optional)

**Azure OpenAI:**
- `AZURE_OPENAI_ENDPOINT` (required)
- `AZURE_OPENAI_DEPLOYMENT_NAME` (required)
- `AZURE_OPENAI_API_KEY` (optional, uses Azure CLI auth if not provided)
- `AZURE_OPENAI_API_VERSION` (optional, default: `2025-03-01-preview`)

## Architecture

Butler Agent is built on proven patterns from the OSDU community:

- **Agent Framework**: Microsoft Agent Framework for structured LLM interactions
- **Multi-Provider Support**: Flexible LLM provider selection via factory pattern
- **Tool-Based Architecture**: Extensible tool system for cluster operations
- **Middleware Pipeline**: Agent and function-level middleware for logging and observability
- **Memory System**: Context providers for learning user preferences and patterns
- **Conversation Persistence**: Thread serialization for saving/loading conversations
- **Rich Console**: Beautiful formatting with Rich library

### Components

```
butler-agent/
├── src/butler/
│   ├── agent.py           # Core agent with LLM orchestration
│   ├── cli.py             # CLI interface and interactive mode
│   ├── config.py          # Multi-provider configuration
│   ├── clients.py         # LLM client factory
│   ├── middleware.py      # Agent and function middleware pipeline
│   ├── memory.py          # Context providers for learning preferences
│   ├── persistence.py     # Conversation save/load management
│   ├── activity.py        # Activity tracking
│   ├── observability.py   # Telemetry integration
│   ├── cluster/           # Cluster management
│   │   ├── tools.py       # Agent tools for cluster ops
│   │   ├── kind_manager.py # KinD CLI wrapper
│   │   ├── status.py      # Status and health checks
│   │   └── config.py      # Cluster templates
│   ├── display/           # Output formatting
│   └── utils/             # Utilities
```

## Development

### CI/CD Pipeline

Butler Agent uses GitHub Actions for automated quality checks, security scanning, and releases:

**CI Workflow**: Runs on every push and pull request
- Black code formatting validation
- Ruff linting checks
- MyPy type checking
- Pytest with coverage (minimum 60% required)
- Quality check summary with actionable guidance

**Security Workflow**: Runs on PRs, weekly schedule, and main branch pushes
- CodeQL security analysis
- Dependency vulnerability scanning
- SBOM (Software Bill of Materials) generation

**Release Workflow**: Automated semantic versioning and releases
- Uses [release-please](https://github.com/googleapis/release-please) for automated changelog generation
- Follows [Conventional Commits](https://www.conventionalcommits.org/) specification
- Automatically builds and uploads Python distribution packages

### Running Quality Checks Locally

Before pushing code, run the same checks that CI will perform:

```bash
# Check code formatting
uv run black --check src/butler/ tests/ --diff --color

# Run linting
uv run ruff check src/butler/ tests/

# Type checking
uv run mypy src/butler --pretty --color-output

# Run tests with coverage
uv run pytest --cov=src/butler --cov-report=xml --cov-report=term-missing --cov-fail-under=60 -v
```

To automatically fix formatting issues:
```bash
uv run black src/butler/ tests/
```

### Running Tests

```bash
# Unit tests
uv run pytest tests/unit/ --cov=butler

# Integration tests (requires Docker)
uv run pytest tests/integration/ -v

# All tests with coverage report
uv run pytest --cov=butler --cov-report=html
```

### Release Process

Butler Agent uses automated releases via Conventional Commits:

1. Use conventional commit messages in your PRs:
   - `feat:` - New features (bumps minor version: 0.1.0 → 0.2.0)
   - `fix:` - Bug fixes (bumps patch version: 0.1.0 → 0.1.1)
   - `feat!:` or `BREAKING CHANGE:` - Breaking changes (bumps major version when >=1.0.0)
   - `docs:`, `test:`, `chore:`, `refactor:`, `ci:` - Included in changelog, no version bump

2. When commits are merged to `main`, release-please automatically:
   - Creates/updates a release PR with changelog and version bump
   - When the release PR is merged, creates a GitHub release
   - Builds and uploads Python wheel and source distributions

For more details on CI/CD workflows, see [docs/ci-cd.md](docs/ci-cd.md).

## Comparison with Related Projects

### vs. HostK8s
- **HostK8s**: Make-based infrastructure management with GitOps
- **Butler**: Conversational interface to HostK8s capabilities (Phase 1: clusters only)
- **Relationship**: Butler will provide natural language interface to HostK8s in future phases

### vs. OSDU Agent
- **OSDU Agent**: Conversational interface for OSDU code and development
- **Butler**: Conversational interface for Kubernetes infrastructure
- **Relationship**: Shared architecture patterns, complementary tools

## Roadmap

### Phase 1: Foundation (Current)
- ✅ Core agent infrastructure
- ✅ KinD cluster management
- ✅ Multi-provider LLM support
- ✅ Basic conversational interface
- ✅ Observability integration

### Phase 2: Component Deployment (Future)
- Component catalog (Istio, Elasticsearch, Postgres, etc.)
- Deployment tools
- Dependency resolution
- Health checking

### Phase 3: GitOps Integration (Future)
- Flux CD management
- Git repository integration
- Kustomization generation

### Phase 4: Software Stacks (Future)
- Pre-configured stack templates
- Stack deployment and validation
- Custom stack creation

### Phase 5: Kubernetes Operations (Future)
- Resource operations
- Log analysis
- Enhanced troubleshooting

## Contributing

Contributions are welcome! Please see the OSDU community guidelines.

## License

Apache 2.0 - See LICENSE file for details.

## Support

- Issues: https://github.com/your-org/butler-agent/issues
- Documentation: See `docs/` directory
- OSDU Community: https://osduforum.org

---

Built with ❤️ by the OSDU Community
