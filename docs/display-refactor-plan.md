# Butler Agent Display Refactor Plan

## Executive Summary

Refactor Butler Agent's display to be **cleaner, more minimal, and event-driven** inspired by OSDU Agent's approach, while maintaining Butler's unique identity as a Kubernetes infrastructure management tool.

## Current State Analysis

### Butler Agent (Current)

**Startup Banner:**
```
╔══════════════════════════════════════╗
║  🤖 Butler                           ║
║  AI-powered DevOps assistant...      ║
╚══════════════════════════════════════╝

Configuration:
• LLM Provider: Azure OpenAI gpt-5-codex
• Data Directory: ./data
• Default K8s Version: v1.34.0

Status:
• Docker: ✓ Connected
• kubectl: ✗ Not available
• kind: ✓ Available
```

**Problems:**
1. **Heavy visual design** - Box characters are outdated and cluttered
2. **Tool checks on init** - Runs subprocess commands during agent initialization (lines 114-159 in cli.py)
3. **Too much information** - Shows configuration details every startup
4. **Inconsistent branding** - Robot emoji doesn't relate to Kubernetes
5. **No execution metrics** - Missing timing, message/tool counts
6. **Static display** - No real-time updates during execution

### OSDU Agent (Reference)

**Startup Banner:**
```
 ◉‿◉  Welcome to OSDU Agent

The OSDU Agent helps manage OSDU services.
The OSDU Agent uses AI, check for mistakes.

 ● Connected to GitLab (community.opengroup.org)
 ● Connected to GitHub (danielscholl-osdu)
 ● Connected to Maven MCP Server (v2.3.0)

 ~/path [⎇ main]                        gpt-5-codex · v0.1.18
────────────────────────────────────────────────────────────
> hi
◉ Complete (4.1s) - msg:2 tool:0

◉‿◉ Hi there! 👋

────────────────────────────────────────────────────────────
```

**Strengths:**
1. **Simple emoticon branding** - ◉‿◉ is memorable and minimal
2. **Clean separators** - Uses simple lines instead of boxes
3. **Execution metrics** - Shows timing and counts
4. **Status bar** - Path, model, version in footer
5. **Event-driven** - Real-time updates via EventEmitter
6. **Progressive disclosure** - Only shows what's needed

## Design Principles for Butler

### 1. Visual Identity

**Butler's Theme: Kubernetes Clusters**
- Use cluster/node themed emoticon: `⎈` (helm/kubernetes symbol) or `☸` (dharma wheel/k8s)
- Alternative: Simple `◉` (node/cluster) or `⚙` (operations)

**Recommendation: Use `☸` for Kubernetes theme**
```
 ☸  Welcome to Butler

Butler helps manage Kubernetes infrastructure.
Butler uses AI - verify all operations.
```

### 2. Banner Simplification

**Before (Heavy - 13 lines):**
```
╔══════════════════════════════════════╗
║  🤖 Butler                           ║
║  AI-powered DevOps assistant...      ║
╚══════════════════════════════════════╝

Configuration:
• LLM Provider: Azure OpenAI gpt-5-codex
• Data Directory: ./data
• Default K8s Version: v1.34.0

Status:
• Docker: ✓ Connected
• kubectl: ✗ Not available
• kind: ✓ Available
```

**After (Minimal - 3-4 lines):**
```
 ☸  Welcome to Butler

Butler manages Kubernetes clusters locally.
Butler uses AI - verify all operations.

 ~/source/github/danielscholl/butler-agent [⎇ main]     gpt-5-codex · v0.1.0
────────────────────────────────────────────────────────────────────────────────
```

### 3. Status Bar Design

**Status Bar Components:**
- Current directory + git branch (like OSDU)
- Model name (from config)
- Butler version (from __version__)

**Format:**
```
 {cwd} [⎇ {branch}]                                    {model} · v{version}
```

### 4. Health Checks - New CLI Command

**Remove from init, create dedicated command:**

```bash
# New command structure
butler check              # Check all dependencies
butler check docker       # Check specific tool
butler check kubectl
butler check kind
```

**Output Format:**
```bash
$ butler check

 ☸  Butler Health Check

Dependencies:
 ● Docker: ✓ Connected (v24.0.0)
 ● kubectl: ✓ Available (v1.28.0)
 ● kind: ✓ Available (v0.20.0)

Environment:
 ● Provider: Azure OpenAI (gpt-5-codex)
 ● Data Dir: ./data (exists, writable)
 ● K8s Version: v1.34.0

All checks passed!
```

### 5. Execution Display

**Before:**
```
Butler (azure)> create cluster dev

[Thinking... spinner]

Response:

<markdown response>

(2 messages in conversation)
```

**After (OSDU-inspired):**
```
────────────────────────────────────────────────────────────────────────────────
> create cluster dev
☸ Complete (3.2s) - msg:2 tool:1


☸ Cluster 'dev' created successfully with 2 nodes
  • Kubeconfig: ./data/dev/kubeconfig
  • Nodes: 1 control-plane, 1 worker

────────────────────────────────────────────────────────────────────────────────
```

### 6. Prompt Design

**Before:** `Butler (azure)> `
**After:** `> ` (clean, minimal)

Provider info goes in status bar, not prompt.

## Implementation Plan

### Phase 1: Remove Tool Checks from Init (Quick Win)

**File:** `src/agent/cli.py`

1. Remove lines 114-159 from `_render_startup_banner()`
2. Keep simple welcome message
3. Remove subprocess imports from banner function

**Impact:** Faster startup, cleaner separation of concerns

### Phase 2: Simplify Banner (Visual Improvement)

**File:** `src/agent/cli.py`

1. Replace box characters with simple text
2. Use `☸` symbol for branding
3. Remove configuration display (move to `butler config` command)
4. Add disclaimer about AI verification

**New Banner:**
```python
def _render_startup_banner() -> None:
    """Render minimal startup banner."""
    banner = """
 [bold cyan]☸  Welcome to Butler[/bold cyan]

Butler manages Kubernetes clusters locally with natural language.
[dim]Butler uses AI - always verify operations before executing.[/dim]
"""
    console.print(banner)
```

### Phase 3: Add Status Bar (Footer)

**File:** `src/agent/cli.py`

Create new function:
```python
def _render_status_bar(config: AgentConfig) -> None:
    """Render status bar with context info."""
    import subprocess
    from pathlib import Path

    # Get current directory
    cwd = Path.cwd().relative_to(Path.home(), fallback=Path.cwd())

    # Get git branch if in repo
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        branch = result.stdout.strip() if result.returncode == 0 else ""
        branch_display = f" [⎇ {branch}]" if branch else ""
    except:
        branch_display = ""

    # Format status bar
    left = f" ~/{cwd}{branch_display}"
    right = f"{config.model_name} · v{__version__}"

    # Calculate padding
    width = console.width
    padding = width - len(left) - len(right)

    console.print(f"[dim]{left}{' ' * padding}{right}[/dim]")
    console.print("[dim]{'─' * width}[/dim]")
```

### Phase 4: Add Health Check Command

**File:** `src/agent/cli.py`

Add to argument parser:
```python
parser.add_argument(
    "command",
    nargs="?",
    choices=["check", "config", "version"],
    help="Command to execute"
)
```

Create new command handler:
```python
async def run_check_command(target: str | None = None) -> None:
    """Run health check command.

    Args:
        target: Specific tool to check (docker, kubectl, kind) or None for all
    """
    console.print("\n [bold cyan]☸  Butler Health Check[/bold cyan]\n")

    # Check dependencies
    console.print("[bold]Dependencies:[/bold]")

    tools = {
        "docker": ["docker", "info"],
        "kubectl": ["kubectl", "version", "--client", "--short"],
        "kind": ["kind", "version"],
    }

    for tool_name, command in tools.items():
        if target and target != tool_name:
            continue

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Extract version if available
                version = _extract_version(result.stdout)
                version_display = f" ({version})" if version else ""
                console.print(f" [green]●[/green] {tool_name}: ✓ Available{version_display}")
            else:
                console.print(f" [red]●[/red] {tool_name}: ✗ Not available")
        except FileNotFoundError:
            console.print(f" [red]●[/red] {tool_name}: ✗ Not installed")
        except Exception as e:
            console.print(f" [yellow]●[/yellow] {tool_name}: ⚠ Check failed ({e})")

    # Check environment
    config = AgentConfig()
    console.print("\n[bold]Environment:[/bold]")
    console.print(f" [cyan]●[/cyan] Provider: {config.get_provider_display_name()}")

    data_dir = Path(config.data_dir)
    if data_dir.exists() and data_dir.is_dir():
        writable = os.access(data_dir, os.W_OK)
        status = "exists, writable" if writable else "exists, read-only"
        console.print(f" [cyan]●[/cyan] Data Dir: {config.data_dir} ({status})")
    else:
        console.print(f" [yellow]●[/yellow] Data Dir: {config.data_dir} (will be created)")

    console.print(f" [cyan]●[/cyan] K8s Version: {config.default_k8s_version}")

    console.print()
```

### Phase 5: Add Execution Metrics

**File:** `src/agent/cli.py`

Track timing and display metrics:
```python
import time

# In interactive loop
start_time = time.time()
response = await agent.run(user_input, thread=thread)
elapsed = time.time() - start_time
message_count += 1

# Count tool calls from thread if available
tool_count = _count_tool_calls(thread)

# Display metrics
console.print(f"\n[cyan]☸[/cyan] Complete ({elapsed:.1f}s) - msg:{message_count} tool:{tool_count}\n")
```

### Phase 6: Event-Driven Display (Advanced - Optional)

**Future Enhancement:** Implement OSDU-style execution tree

This would require:
1. Create `display/events.py` - Event emitter
2. Create `display/execution_tree.py` - Tree renderer
3. Modify agent middleware to emit events
4. Add display modes (minimal, default, verbose)

**Complexity:** High
**Benefit:** Real-time progress updates during long operations
**Priority:** Low (nice-to-have)

## CLI Command Structure

### Current
```bash
butler                    # Interactive mode
butler -p "query"         # Single query
butler -q                 # Quiet mode
butler -v                 # Verbose mode
butler --version          # Show version
```

### Proposed (OSDU-inspired)
```bash
butler                    # Interactive mode
butler -p "query"         # Single query
butler -q                 # Quiet mode
butler -v                 # Verbose mode

# New commands
butler check              # Health check all
butler check docker       # Check specific tool
butler config             # Show configuration
butler version            # Show version (detailed)
```

## Configuration Command

**New command:**
```bash
$ butler config

 ☸  Butler Configuration

LLM Provider:
 • Provider: Azure OpenAI
 • Model: gpt-5-codex
 • Endpoint: https://your-resource.openai.azure.com/
 • Deployment: gpt-5-codex

Agent Settings:
 • Data Directory: ./data
 • Cluster Prefix: butler-
 • Default K8s Version: v1.34.0
 • Log Level: info

Observability:
 • Application Insights: Not configured
```

## Files to Modify

### Primary Changes
1. **src/agent/cli.py** (main refactor)
   - Simplify `_render_startup_banner()` (lines 92-162)
   - Add `_render_status_bar()`
   - Add `run_check_command()`
   - Add `run_config_command()`
   - Update `build_parser()` to support subcommands
   - Simplify `_render_prompt_area()` (line 165-174)
   - Add execution metrics display

### Optional/Future
2. **src/agent/display/events.py** (new - event emitter)
3. **src/agent/display/execution_tree.py** (new - tree renderer)
4. **src/agent/display/terminal.py** (new - terminal utilities)

### Unchanged
- **src/agent/display/formatters.py** (keep for tool responses)
- **src/agent/display/tables.py** (keep for structured data)
- **src/agent/agent.py** (no changes needed)
- **src/agent/config.py** (no changes needed)

## Timeline Estimate

**Phase 1-3 (Essential):** 2-3 hours
- Remove tool checks from init
- Simplify banner
- Add status bar

**Phase 4 (Important):** 1-2 hours
- Add health check command
- Add config command

**Phase 5 (Nice-to-have):** 1 hour
- Add execution metrics

**Phase 6 (Future):** 8-12 hours
- Event-driven display system

**Total for Essential Changes:** 4-6 hours

## Recommendation

**Start with Phases 1-5** (Essential + Metrics)
- High impact, low risk
- Significantly improves UX
- Maintains compatibility
- Clean separation of concerns

**Defer Phase 6** (Event-driven display)
- High complexity
- Lower immediate benefit
- Can be added later if needed
- Butler doesn't have as many long-running operations as OSDU

## Key Differences: Butler vs OSDU

| Aspect | OSDU Agent | Butler Agent |
|--------|-----------|--------------|
| **Domain** | Code/OSDU services | Kubernetes clusters |
| **Symbol** | ◉‿◉ (friendly) | ☸ (kubernetes) |
| **Operations** | Many tools, long-running | Fewer tools, faster ops |
| **Complexity** | High (needs execution tree) | Medium (simple metrics ok) |
| **Priority** | Development workflow | Infrastructure management |

**Butler can be simpler than OSDU** - We don't need the full execution tree complexity since cluster operations are generally faster and simpler than code operations.

## Final Recommendations

### What to Adopt from OSDU
✅ Minimal banner design
✅ Status bar with context
✅ Clean separators
✅ Execution metrics (timing, counts)
✅ Simple prompt
✅ Health checks as separate command

### What to Skip
❌ Full execution tree (overkill for Butler)
❌ Complex event system (not needed yet)
❌ Multiple display modes (start simple)

### Butler's Unique Identity
- Use ☸ (Kubernetes symbol) for branding
- Focus on cluster operations
- Keep it infrastructure-focused
- Simpler is better for DevOps tools

**Butler should be: Clean, Fast, Minimal, Professional**
