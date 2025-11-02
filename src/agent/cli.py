"""CLI interface for Butler Agent.

This module provides the command-line interface with interactive chat mode
and single-query execution.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

from agent import __version__
from agent.agent import Agent
from agent.config import AgentConfig
from agent.observability import initialize_observability
from agent.persistence import ThreadPersistence
from agent.utils.errors import ConfigurationError

console = Console()


def setup_logging(log_level: str = "info") -> None:
    """Setup logging with Rich handler.

    Args:
        log_level: Logging level (debug, info, warning, error)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=console,
                show_time=False,
                show_path=False,
                rich_tracebacks=True,
            )
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Butler - AI-powered Kubernetes infrastructure management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="Execute a single prompt and exit",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimal output mode",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output with detailed execution information",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Run health check for dependencies and configuration",
    )

    parser.add_argument(
        "--config",
        action="store_true",
        help="Show current configuration",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Butler Agent {__version__}",
    )

    return parser


def _render_startup_banner(config: AgentConfig) -> None:
    """Render minimal startup banner.

    Args:
        config: Agent configuration
    """
    banner = """
 [bold cyan]☸  Welcome to Butler[/bold cyan]

Butler manages Kubernetes clusters locally with natural language.
[dim]Butler uses AI - always verify operations before executing.[/dim]
"""
    console.print(banner)


def _render_status_bar(config: AgentConfig) -> None:
    """Render status bar with context info.

    Args:
        config: Agent configuration
    """
    import subprocess

    # Get current directory relative to home
    try:
        cwd = Path.cwd().relative_to(Path.home())
        cwd_display = f"~/{cwd}"
    except ValueError:
        # Not relative to home, use absolute path
        cwd_display = str(Path.cwd())

    # Get git branch if in repo
    branch_display = ""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch:
                branch_display = f" [⎇ {branch}]"
    except Exception:
        # Ignore git errors - branch display is optional
        pass

    # Format status bar
    left = f" {cwd_display}{branch_display}"
    right = f"{config.model_name} · v{__version__}"

    # Calculate padding to align right side
    width = console.width
    padding = max(1, width - len(left) - len(right))

    console.print(f"[dim]{left}[/dim]{' ' * padding}[cyan]{right}[/cyan]", highlight=False)
    console.print(f"[dim]{'─' * width}[/dim]")


def _render_prompt_area() -> str:
    """Render prompt area.

    Returns:
        Prompt string
    """
    return "> "


def _count_tool_calls(thread: Any) -> int:
    """Count tool calls in the thread.

    Args:
        thread: Agent thread object

    Returns:
        Number of tool calls
    """
    try:
        # Try to access messages from thread
        if not hasattr(thread, "messages"):
            return 0

        tool_count = 0
        for message in thread.messages:
            # Check for tool calls in message
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_count += len(message.tool_calls)
            # Alternative: check for function_call
            elif hasattr(message, "function_call") and message.function_call:
                tool_count += 1

        return tool_count
    except Exception:
        # If we can't count, return 0
        return 0


def _render_completion_status(elapsed: float, message_count: int, tool_count: int) -> None:
    """Render completion status with metrics.

    Args:
        elapsed: Elapsed time in seconds
        message_count: Number of messages in conversation
        tool_count: Number of tool calls
    """
    console.print(
        f"[cyan]☸[/cyan] Complete ({elapsed:.1f}s) - msg:{message_count} tool:{tool_count}\n",
        highlight=False,
    )


async def run_chat_mode(quiet: bool = False, verbose: bool = False) -> None:
    """Run interactive chat mode.

    Args:
        quiet: Minimal output mode
        verbose: Verbose output mode
    """
    try:
        # Load configuration
        config = AgentConfig()
        config.validate()

        # Setup logging
        log_level = "debug" if verbose else config.log_level
        setup_logging(log_level)

        # Initialize observability
        if config.applicationinsights_connection_string:
            initialize_observability(config.applicationinsights_connection_string)

        # Show startup banner
        if not quiet:
            _render_startup_banner(config)
            _render_status_bar(config)

        # Create agent
        try:
            agent = Agent(config)
        except Exception as e:
            console.print(f"[red]Failed to initialize agent: {e}[/red]")
            sys.exit(1)

        # Create conversation thread for multi-turn conversations
        thread = agent.get_new_thread()
        message_count = 0

        # Initialize persistence manager
        persistence = ThreadPersistence()

        # Setup prompt session with history
        history_file = Path.home() / ".butler_history"
        session: PromptSession = PromptSession(history=FileHistory(str(history_file)))

        # Interactive loop
        while True:
            try:
                # Get user input
                prompt_text = _render_prompt_area()
                user_input = await session.prompt_async(prompt_text)

                if not user_input or not user_input.strip():
                    continue

                # Handle special commands
                cmd = user_input.strip().lower()

                if cmd in ["exit", "quit", "q"]:
                    console.print("[dim]Goodbye! 👋[/dim]")
                    break

                if cmd in ["help", "?"]:
                    _show_help()
                    continue

                if cmd == "clear":
                    console.clear()
                    if not quiet:
                        _render_startup_banner(config)
                        _render_status_bar(config)
                    continue

                # Handle /new command to start fresh conversation
                if cmd in ["/new", "new"]:
                    thread = agent.get_new_thread()
                    message_count = 0
                    console.print("[green]✓ Started new conversation[/green]\n")
                    continue

                # Handle /save command to save conversation
                if user_input.startswith("/save"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[red]Usage: /save <name>[/red]")
                        continue

                    name = parts[1].strip()
                    try:
                        await persistence.save_thread(thread, name)
                        console.print(f"[green]✓ Conversation saved as '{name}'[/green]\n")
                    except Exception as e:
                        console.print(f"[red]Failed to save conversation: {e}[/red]\n")
                        if verbose:
                            console.print_exception()
                    continue

                # Handle /load command to load conversation
                if user_input.startswith("/load"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[red]Usage: /load <name>[/red]")
                        continue

                    name = parts[1].strip()
                    try:
                        thread = await persistence.load_thread(agent, name)
                        # Try to get message count from thread if possible
                        message_count = len(thread.messages) if hasattr(thread, "messages") else 0
                        console.print(
                            f"[green]✓ Conversation '{name}' loaded "
                            f"({message_count} messages)[/green]\n"
                        )
                    except FileNotFoundError:
                        console.print(f"[red]Conversation '{name}' not found[/red]\n")
                    except Exception as e:
                        console.print(f"[red]Failed to load conversation: {e}[/red]\n")
                        if verbose:
                            console.print_exception()
                    continue

                # Handle /list command to list saved conversations
                if cmd == "/list":
                    conversations = persistence.list_conversations()
                    if conversations:
                        console.print("\n[bold]Saved Conversations:[/bold]")
                        for conv in conversations:
                            desc = conv.get("description") or "[dim]No description[/dim]"
                            created = conv.get("created_at", "")[:10]  # Just date
                            console.print(f"  • [cyan]{conv['name']}[/cyan] ({created})")
                            if conv.get("description"):
                                console.print(f"    {desc}")
                    else:
                        console.print("[dim]No saved conversations[/dim]")
                    console.print()
                    continue

                # Handle /delete command to delete saved conversation
                if user_input.startswith("/delete"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[red]Usage: /delete <name>[/red]")
                        continue

                    name = parts[1].strip()
                    try:
                        if persistence.delete_conversation(name):
                            console.print(f"[green]✓ Conversation '{name}' deleted[/green]\n")
                        else:
                            console.print(f"[red]Conversation '{name}' not found[/red]\n")
                    except Exception as e:
                        console.print(f"[red]Failed to delete conversation: {e}[/red]\n")
                        if verbose:
                            console.print_exception()
                    continue

                # Execute query with conversation thread
                import time

                start_time = time.time()

                with console.status("[bold blue]Thinking...", spinner="dots"):
                    response = await agent.run(user_input, thread=thread)
                    message_count += 1

                elapsed = time.time() - start_time
                tool_count = _count_tool_calls(thread)

                # Display completion status with metrics
                if not quiet:
                    _render_completion_status(elapsed, message_count, tool_count)

                # Display response
                if response:
                    console.print()
                    console.print(Markdown(response))
                    console.print()

                    # Add separator line
                    if not quiet:
                        console.print(f"[dim]{'─' * console.width}[/dim]")

            except KeyboardInterrupt:
                console.print("\n[dim]Use 'exit' to quit[/dim]")
                continue

            except EOFError:
                console.print("\n[dim]Goodbye! 👋[/dim]")
                break

            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]\n")
                if verbose:
                    console.print_exception()

    except ConfigurationError as e:
        console.print(f"[red]Configuration Error: {e}[/red]")
        console.print("\n[yellow]Please check your .env file or environment variables.[/yellow]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Fatal Error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


async def run_single_query(prompt: str, quiet: bool = False, verbose: bool = False) -> None:
    """Run a single query and exit.

    Args:
        prompt: Query to execute
        quiet: Minimal output mode
        verbose: Verbose output mode
    """
    try:
        # Load configuration
        config = AgentConfig()
        config.validate()

        # Setup logging
        log_level = "debug" if verbose else config.log_level
        setup_logging(log_level)

        # Initialize observability
        if config.applicationinsights_connection_string:
            initialize_observability(config.applicationinsights_connection_string)

        # Create agent
        try:
            agent = Agent(config)
        except Exception as e:
            console.print(f"[red]Failed to initialize agent: {e}[/red]")
            sys.exit(1)

        # Execute query (single-turn, no thread persistence needed)
        import time

        if not quiet:
            console.print(f"\n[bold cyan]Query:[/bold cyan] {prompt}\n")

        start_time = time.time()
        thread = agent.get_new_thread()

        with console.status("[bold blue]Thinking...", spinner="dots"):
            response = await agent.run(prompt, thread=thread)

        elapsed = time.time() - start_time
        tool_count = _count_tool_calls(thread)

        # Display completion status with metrics
        if not quiet:
            _render_completion_status(elapsed, 1, tool_count)

        # Display response
        if response:
            console.print()
            console.print(Markdown(response))
            console.print()

            # Add separator line
            if not quiet:
                console.print(f"[dim]{'─' * console.width}[/dim]")

    except ConfigurationError as e:
        console.print(f"[red]Configuration Error: {e}[/red]")
        console.print("\n[yellow]Please check your .env file or environment variables.[/yellow]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


def _show_help() -> None:
    """Show help information."""
    help_text = """
# Butler Agent Help

## CLI Commands

- `butler` - Start interactive chat mode
- `butler --check` - Run health check for dependencies and configuration
- `butler --config` - Show current configuration
- `butler -p "query"` - Execute single query and exit
- `butler -v` - Enable verbose output
- `butler -q` - Enable quiet mode (minimal output)

## Interactive Commands

- **exit, quit, q** - Exit Butler
- **help, ?** - Show this help
- **clear** - Clear screen
- **/new** - Start a new conversation (reset context)
- **/save <name>** - Save current conversation
- **/load <name>** - Load a saved conversation
- **/list** - List all saved conversations
- **/delete <name>** - Delete a saved conversation

## Example Queries

- "Create a cluster called dev-env"
- "What clusters do I have?"
- "Show status for dev-env"
- "Delete the test-cluster"
- "Create a minimal cluster called quick-test"

## Health Check

Verify dependencies and configuration:
```bash
butler --check
```

## Conversation Management

Save your work and resume later:
```
/save my-dev-setup
/list
/load my-dev-setup
```

## Tips

- Cluster names should be lowercase with hyphens
- You can specify cluster configuration: minimal, default, or custom
- Conversations are saved to ~/.butler/conversations/
- Use `butler --config` to verify your LLM provider settings
    """

    console.print(Markdown(help_text))


def _extract_version(output: str) -> str:
    """Extract version from command output.

    Args:
        output: Command output containing version info

    Returns:
        Version string or empty string if not found
    """
    import re

    # Try to find version patterns like v1.2.3 or 1.2.3
    match = re.search(r"v?(\d+\.\d+\.\d+)", output)
    return match.group(0) if match else ""


def run_check_command() -> None:
    """Run health check command."""
    import os
    import subprocess

    console.print("\n [bold cyan]☸  Butler Health Check[/bold cyan]\n")

    # Check dependencies
    console.print("[bold]Dependencies:[/bold]")

    tools = {
        "docker": (["docker", "info"], True),  # (command, required)
        "kubectl": (["kubectl", "version", "--client"], False),
        "kind": (["kind", "version"], False),
    }

    all_passed = True

    for tool_name, (command, required) in tools.items():

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
                version_display = f" [cyan]({version})[/cyan]" if version else ""
                console.print(
                    f" [green]●[/green] {tool_name}: ✓ Available{version_display}",
                    highlight=False,
                )
            else:
                all_passed = False if required else all_passed
                style = "red" if required else "yellow"
                console.print(
                    f" [{style}]●[/{style}] {tool_name}: ✗ Not available", highlight=False
                )
        except FileNotFoundError:
            all_passed = False if required else all_passed
            style = "red" if required else "yellow"
            console.print(f" [{style}]●[/{style}] {tool_name}: ✗ Not installed", highlight=False)
        except Exception as e:
            all_passed = False if required else all_passed
            console.print(f" [yellow]●[/yellow] {tool_name}: ⚠ Check failed ({e})", highlight=False)

    # Check environment
    try:
        config = AgentConfig()
        console.print("\n[bold]Environment:[/bold]")
        console.print(
            f" [cyan]●[/cyan] Provider: [cyan]{config.get_provider_display_name()}[/cyan]",
            highlight=False,
        )

        data_dir = Path(config.data_dir)
        if data_dir.exists() and data_dir.is_dir():
            writable = os.access(data_dir, os.W_OK)
            status = "exists, writable" if writable else "exists, read-only"
            console.print(
                f" [cyan]●[/cyan] Data Dir: [magenta]{config.data_dir}[/magenta] ({status})",
                highlight=False,
            )
        else:
            console.print(
                f" [yellow]●[/yellow] Data Dir: [magenta]{config.data_dir}[/magenta] (will be created)",
                highlight=False,
            )

        console.print(
            f" [cyan]●[/cyan] K8s Version: [cyan]{config.default_k8s_version}[/cyan]",
            highlight=False,
        )

    except Exception as e:
        console.print(f" [red]●[/red] Configuration: ✗ Invalid ({e})", highlight=False)
        all_passed = False

    # Summary
    if all_passed:
        console.print("\n[green]✓ All checks passed![/green]\n")
    else:
        console.print("\n[yellow]⚠ Some checks failed[/yellow]\n")


def run_config_command() -> None:
    """Show current configuration."""
    console.print("\n [bold cyan]☸  Butler Configuration[/bold cyan]\n")

    try:
        config = AgentConfig()

        # LLM Provider section
        console.print("[bold]LLM Provider:[/bold]")
        if config.llm_provider == "azure":
            console.print(" • Provider: [cyan]Azure OpenAI[/cyan]", highlight=False)
            console.print(f" • Model: [cyan]{config.model_name}[/cyan]", highlight=False)
            console.print(
                f" • Endpoint: [cyan]{config.azure_openai_endpoint}[/cyan]", highlight=False
            )
            console.print(
                f" • Deployment: [cyan]{config.azure_openai_deployment}[/cyan]", highlight=False
            )
            console.print(
                f" • API Version: [cyan]{config.azure_openai_api_version}[/cyan]",
                highlight=False,
            )
            if config.azure_openai_api_key:
                console.print(" • Auth: [cyan]API Key[/cyan]", highlight=False)
            else:
                console.print(" • Auth: [cyan]Azure CLI / Managed Identity[/cyan]", highlight=False)
        elif config.llm_provider == "openai":
            console.print(" • Provider: [cyan]OpenAI[/cyan]", highlight=False)
            console.print(f" • Model: [cyan]{config.model_name}[/cyan]", highlight=False)
            if config.openai_base_url:
                console.print(
                    f" • Base URL: [cyan]{config.openai_base_url}[/cyan]", highlight=False
                )
            if config.openai_organization:
                console.print(
                    f" • Organization: [cyan]{config.openai_organization}[/cyan]", highlight=False
                )

        # Agent Settings section
        console.print("\n[bold]Agent Settings:[/bold]")
        console.print(f" • Data Directory: [cyan]{config.data_dir}[/cyan]", highlight=False)
        console.print(f" • Cluster Prefix: [cyan]{config.cluster_prefix}[/cyan]", highlight=False)
        console.print(
            f" • Default K8s Version: [cyan]{config.default_k8s_version}[/cyan]", highlight=False
        )
        console.print(f" • Log Level: [cyan]{config.log_level}[/cyan]", highlight=False)

        # Observability section
        console.print("\n[bold]Observability:[/bold]")
        if config.applicationinsights_connection_string:
            console.print(" • Application Insights: [green]Configured[/green]")
        else:
            console.print(" • Application Insights: [dim]Not configured[/dim]")

        console.print()

    except ConfigurationError as e:
        console.print(f"[red]Configuration Error: {e}[/red]\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]\n")
        sys.exit(1)


async def async_main() -> None:
    """Async main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Handle check command
    if args.check:
        run_check_command()
        return

    # Handle config command
    if args.config:
        run_config_command()
        return

    # Handle single query mode
    if args.prompt:
        await run_single_query(args.prompt, quiet=args.quiet, verbose=args.verbose)
    else:
        # Interactive chat mode
        await run_chat_mode(quiet=args.quiet, verbose=args.verbose)


def main() -> None:
    """Main entry point for CLI."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
