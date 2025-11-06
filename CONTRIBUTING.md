# Contributing to Butler Agent

Thank you for your interest in contributing to Butler Agent!

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (running)
- Git
- Azure CLI (`az`) for Azure OpenAI authentication (optional)

### Initial Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/danielscholl/butler-agent.git
   cd butler-agent
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Verify installation:
   ```bash
   uv run butler --help
   ```

### Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Configure required environment variables:

```bash
# Required
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-codex

# Optional
BUTLER_DATA_DIR=.local
BUTLER_DEFAULT_K8S_VERSION=v1.34.0
LOG_LEVEL=info
```

## Code Quality

### Quality Checks

Before submitting a pull request, ensure all quality checks pass:

```bash
# Auto-fix formatting and linting
uv run black src/agent/ tests/
uv run ruff check --fix src/agent/ tests/

# Verify checks pass
uv run black --check src/agent/ tests/
uv run ruff check src/agent/ tests/
uv run mypy src/agent/
uv run pytest --cov=src/agent --cov-fail-under=60
```

### CI Pipeline

Our GitHub Actions CI runs the following checks:

1. **Black**: Code formatting (strict)
2. **Ruff**: Linting and code quality
3. **MyPy**: Type checking
4. **PyTest**: Test suite with 60% minimum coverage
5. **CodeQL**: Security scanning

All checks must pass for PRs to be merged.

### Testing

#### Run All Tests

```bash
# Full test suite
uv run pytest

# With verbose output
uv run pytest -v

# With coverage report
uv run pytest --cov=src/agent --cov-report=term-missing
```

#### Run Specific Tests

```bash
# Test a specific file
uv run pytest tests/unit/test_agent.py

# Test a specific class
uv run pytest tests/unit/test_cli.py::TestInteractiveMode

# Test a specific function
uv run pytest tests/unit/test_config.py::test_azure_provider_validation
```

#### Coverage

```bash
# Generate HTML coverage report
uv run pytest --cov=src/agent --cov-report=html
open htmlcov/index.html
```

## Commit Guidelines

This project uses [Conventional Commits](https://www.conventionalcommits.org/) with [Release Please](https://github.com/googleapis/release-please) for automated versioning.

### Commit Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Commit Types

- `feat`: New feature (triggers minor version bump)
- `fix`: Bug fix (triggers patch version bump)
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

### Breaking Changes

For breaking changes, add `!` after type or add `BREAKING CHANGE:` in footer:

```
feat!: redesign CLI interface

BREAKING CHANGE: The --prompt flag is now -p.
Removed deprecated --service flag.
```

### Examples

```bash
feat(cluster): add custom cluster configuration support
fix(cli): handle missing .env file gracefully
docs(readme): update installation instructions
test(memory): add conversation persistence tests
chore(deps): update agent-framework to 1.0.0
```

## Architecture

Butler Agent follows a modular architecture built on Microsoft Agent Framework.

### Core Components

#### Agent Layer (`src/agent/`)
- **agent.py**: Main Agent class with LLM orchestration
- **config.py**: Multi-provider configuration management
- **cli.py**: CLI interface and interactive chat mode
- **clients.py**: LLM client factory (OpenAI, Azure OpenAI)

#### Cluster Management (`src/agent/cluster/`)
- **tools.py**: Agent tools for cluster operations (create, delete, status, health)
- **kind_manager.py**: KinD CLI wrapper
- **status.py**: Cluster health checks and status monitoring
- **config.py**: Cluster configuration templates (minimal, default, custom)

#### Memory & Context (`src/agent/`)
- **memory.py**: Context providers for learning user preferences
  - `ClusterMemory`: Remembers cluster preferences and patterns
  - `ConversationMetricsMemory`: Tracks session statistics
- **persistence.py**: Conversation save/load management
- **middleware.py**: Agent and function-level middleware for logging

#### Display & Observability
- **display/**: Rich console formatting (formatters, tables, progress)
- **observability.py**: Azure Application Insights integration
- **activity.py**: Activity tracking

## Development Workflows

### Adding a New Cluster Tool

1. Add tool function in `src/agent/cluster/tools.py`
2. Add type hints and comprehensive docstring
3. Add to `CLUSTER_TOOLS` list
4. Add unit tests in `tests/unit/`
5. Update documentation

### Adding a CLI Command

1. Add argument to `build_parser()` in `src/agent/cli.py`
2. Create command handler function
3. Add routing in `async_main()`
4. Add tests in `tests/unit/test_cli.py`
5. Update help text

### Modifying Display

Display code is in `src/agent/cli.py` and `src/agent/display/`:
- Banner and status bar: `_render_startup_banner()`, `_render_status_bar()`
- Completion metrics: `_render_completion_status()`
- Keep consistent with ☸ (Kubernetes symbol) branding
- Use `highlight=False` to prevent Rich auto-highlighting

## Pull Request Process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** following code style guidelines

3. **Run quality checks**:
   ```bash
   uv run black src/agent/ tests/
   uv run ruff check --fix src/agent/ tests/
   uv run mypy src/agent/
   uv run pytest --cov=src/agent
   ```

4. **Commit using aipr** (if available):
   ```bash
   git add .
   git commit -m "$(aipr commit -s -m claude)"
   ```

   Or manually with conventional commits:
   ```bash
   git commit -m "feat(scope): add new feature"
   ```

5. **Push and create PR**:
   ```bash
   git push -u origin feat/your-feature-name
   gh pr create --title "feat: add new feature" --body "Description"
   ```

6. **Address review comments** and ensure CI passes

### Code Review Checklist

Reviewers will verify:

- [ ] All CI checks pass (Black, Ruff, MyPy, PyTest, CodeQL)
- [ ] Test coverage ≥ 60%
- [ ] Type hints on all public functions
- [ ] Docstrings for public APIs
- [ ] Conventional commit format
- [ ] No breaking changes without `BREAKING CHANGE:` footer
- [ ] Documentation updated if needed

## Project Structure

```
butler-agent/
├── src/agent/
│   ├── agent.py              # Core agent with LLM orchestration
│   ├── cli.py                # CLI interface and interactive mode
│   ├── config.py             # Multi-provider configuration
│   ├── clients.py            # LLM client factory
│   ├── middleware.py         # Agent and function middleware
│   ├── memory.py             # Context providers for learning
│   ├── persistence.py        # Conversation save/load
│   ├── activity.py           # Activity tracking
│   ├── observability.py      # Telemetry integration
│   ├── cluster/              # Cluster management
│   │   ├── tools.py          # Agent tools
│   │   ├── kind_manager.py   # KinD CLI wrapper
│   │   ├── status.py         # Health checks
│   │   └── config.py         # Cluster templates
│   ├── display/              # Output formatting
│   │   ├── formatters.py     # Format helpers
│   │   ├── tables.py         # Table rendering
│   │   └── progress.py       # Progress indicators
│   ├── prompts/              # System prompts
│   │   └── system.md         # Butler system prompt
│   └── utils/                # Utilities
│       ├── errors.py         # Custom exceptions
│       ├── paths.py          # Path utilities
│       └── validation.py     # Input validation
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── mocks/                # Mock objects
│   │   └── mock_client.py    # Mock LLM client
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
└── docs/
    ├── ci-cd.md              # CI/CD documentation
    ├── ARCHITECTURE_PLAN.md  # Architecture details
    └── display-refactor-plan.md  # Display design decisions
```

## Error Handling

- Use specific exception types from `src/agent/utils/errors.py`
- Provide actionable error messages
- Log errors with context using `logger.error()`
- Tools should return error dicts (not raise) for user-friendly responses

## Troubleshooting

### Tests Failing

```bash
# Clear pytest cache
rm -rf .pytest_cache/ __pycache__/

# Reinstall dependencies
uv sync

# Run tests with verbose output
uv run pytest -xvs
```

### MyPy Errors

```bash
# Check specific file
uv run mypy src/agent/cli.py

# Show error context
uv run mypy src/agent/ --show-error-context
```

### Import Errors

```bash
# Verify package installed
uv run python -c "import agent; print(agent.__file__)"
```

## Getting Help

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/danielscholl/butler-agent/issues)
- **Discussions**: Ask questions in [GitHub Discussions](https://github.com/danielscholl/butler-agent/discussions)
- **Security**: Report vulnerabilities via GitHub Security Advisories

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
