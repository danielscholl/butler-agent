"""CLI interface for Butler Agent.

This module provides the command-line interface with interactive chat mode
and single-query execution.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

from butler import __version__
from butler.agent import ButlerAgent
from butler.config import ButlerConfig
from butler.observability import initialize_observability
from butler.persistence import ThreadPersistence
from butler.utils.errors import ConfigurationError

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
        "--version",
        action="version",
        version=f"Butler Agent {__version__}",
    )

    return parser


def _render_startup_banner(config: ButlerConfig) -> None:
    """Render startup banner with configuration info.

    Args:
        config: Butler configuration
    """
    banner = f"""
    [bold cyan]╔══════════════════════════════════════╗[/bold cyan]
    [bold cyan]║[/bold cyan]  [bold white]🤖 Butler Agent[/bold white]                   [bold cyan]║[/bold cyan]
    [bold cyan]║[/bold cyan]  [white]Your AI-Powered DevOps Assistant[/white]  [bold cyan]║[/bold cyan]
    [bold cyan]╚══════════════════════════════════════╝[/bold cyan]

    [bold]Configuration:[/bold]
    • LLM Provider: [cyan]{config.get_provider_display_name()}[/cyan]
    • Data Directory: [cyan]{config.data_dir}[/cyan]
    • Default K8s Version: [cyan]{config.default_k8s_version}[/cyan]

    [bold]Status:[/bold]
    """

    console.print(banner)

    # Check Docker
    try:
        import subprocess

        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        docker_status = "✓ Connected" if result.returncode == 0 else "✗ Not available"
        docker_style = "green" if result.returncode == 0 else "red"
    except Exception:
        docker_status = "✗ Not available"
        docker_style = "red"

    console.print(f"    • Docker: [{docker_style}]{docker_status}[/{docker_style}]")

    # Check kubectl
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client", "--short"],
            capture_output=True,
            timeout=5,
        )
        kubectl_status = "✓ Available" if result.returncode == 0 else "✗ Not available"
        kubectl_style = "green" if result.returncode == 0 else "yellow"
    except Exception:
        kubectl_status = "✗ Not available"
        kubectl_style = "yellow"

    console.print(f"    • kubectl: [{kubectl_style}]{kubectl_status}[/{kubectl_style}]")

    # Check kind
    try:
        result = subprocess.run(
            ["kind", "version"],
            capture_output=True,
            timeout=5,
        )
        kind_status = "✓ Available" if result.returncode == 0 else "✗ Not available"
        kind_style = "green" if result.returncode == 0 else "yellow"
    except Exception:
        kind_status = "✗ Not available"
        kind_style = "yellow"

    console.print(f"    • kind: [{kind_style}]{kind_status}[/{kind_style}]")

    console.print("\n[dim]Type 'exit' or 'quit' to exit, 'help' for help[/dim]")
    console.print("[dim]Commands: /new /save /load /list /delete - Type 'help' for details[/dim]\n")


def _render_prompt_area(config: ButlerConfig) -> str:
    """Render prompt area with status info.

    Args:
        config: Butler configuration

    Returns:
        Prompt string
    """
    return f"Butler ({config.llm_provider})> "


async def run_chat_mode(quiet: bool = False, verbose: bool = False) -> None:
    """Run interactive chat mode.

    Args:
        quiet: Minimal output mode
        verbose: Verbose output mode
    """
    try:
        # Load configuration
        config = ButlerConfig()
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

        # Create agent
        try:
            agent = ButlerAgent(config)
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
                prompt_text = _render_prompt_area(config)
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
                if not quiet:
                    console.print()

                with console.status("[bold blue]Thinking...", spinner="dots"):
                    response = await agent.run(user_input, thread=thread)
                    message_count += 1

                # Display response
                if response:
                    console.print()
                    console.print(Markdown(response))
                    if not quiet and message_count > 1:
                        console.print(f"\n[dim]({message_count} messages in conversation)[/dim]")
                    console.print()

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
        config = ButlerConfig()
        config.validate()

        # Setup logging
        log_level = "debug" if verbose else config.log_level
        setup_logging(log_level)

        # Initialize observability
        if config.applicationinsights_connection_string:
            initialize_observability(config.applicationinsights_connection_string)

        # Create agent
        try:
            agent = ButlerAgent(config)
        except Exception as e:
            console.print(f"[red]Failed to initialize agent: {e}[/red]")
            sys.exit(1)

        # Execute query (single-turn, no thread persistence needed)
        if not quiet:
            console.print(f"\n[bold cyan]Query:[/bold cyan] {prompt}\n")

        with console.status("[bold blue]Thinking...", spinner="dots"):
            response = await agent.run(prompt)

        # Display response
        if response:
            if not quiet:
                console.print("[bold cyan]Response:[/bold cyan]\n")
            console.print(Markdown(response))
            console.print()

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

## Commands

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
- Use `butler -p "your query"` for single commands
- Use `butler -v` for verbose output with debugging info
- Conversations are saved to ~/.butler/conversations/
    """

    console.print(Markdown(help_text))


async def async_main() -> None:
    """Async main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.prompt:
        # Single query mode
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
