"""Async subprocess utilities for non-blocking command execution.

This module provides async alternatives to subprocess.run() that allow
the event loop to continue running during long-running operations.
"""

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AsyncCompletedProcess:
    """Async version of subprocess.CompletedProcess.

    Mirrors the interface of subprocess.CompletedProcess for compatibility
    with existing code that expects returncode, stdout, stderr attributes.
    """

    args: list[str] | str
    returncode: int
    stdout: str = ""
    stderr: str = ""


async def run_async(
    cmd: list[str],
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    check: bool = False,
    capture_output: bool = True,
) -> AsyncCompletedProcess:
    """Run a command asynchronously without blocking the event loop.

    This is an async alternative to subprocess.run() that allows the event
    loop to continue processing events (like updating the execution tree display)
    while the subprocess is running.

    Args:
        cmd: Command and arguments as a list
        env: Optional environment variables
        timeout: Optional timeout in seconds
        check: If True, raise CalledProcessError on non-zero exit
        capture_output: If True, capture stdout and stderr

    Returns:
        AsyncCompletedProcess with returncode, stdout, stderr

    Raises:
        asyncio.TimeoutError: If command times out
        subprocess.CalledProcessError: If check=True and command fails

    Example:
        result = await run_async(['kind', 'create', 'cluster'], timeout=120)
        if result.returncode == 0:
            print(result.stdout)
    """
    logger.debug(f"Running async command: {' '.join(cmd)}")

    try:
        # Create subprocess with pipes if capturing output
        if capture_output:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
            )

        # Wait for completion with optional timeout
        try:
            if timeout:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate()
        except TimeoutError:
            # Kill the process on timeout
            process.kill()
            await process.wait()
            logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            raise

        # Decode output
        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

        # Create result
        result = AsyncCompletedProcess(
            args=cmd, returncode=process.returncode or 0, stdout=stdout, stderr=stderr
        )

        # Check for errors if requested
        if check and result.returncode != 0:
            import subprocess

            raise subprocess.CalledProcessError(
                returncode=result.returncode,
                cmd=cmd,
                output=stdout,
                stderr=stderr,
            )

        logger.debug(
            f"Command completed: returncode={result.returncode}, "
            f"stdout_len={len(stdout)}, stderr_len={len(stderr)}"
        )

        return result

    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise
    except Exception as e:
        logger.error(f"Error running command: {e}")
        raise


async def run_shell_async(
    command: str,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    check: bool = False,
    capture_output: bool = True,
) -> AsyncCompletedProcess:
    """Run a shell command asynchronously.

    This is similar to run_async but executes the command through a shell,
    allowing shell features like pipes, redirects, etc.

    Args:
        command: Shell command string
        env: Optional environment variables
        timeout: Optional timeout in seconds
        check: If True, raise CalledProcessError on non-zero exit
        capture_output: If True, capture stdout and stderr

    Returns:
        AsyncCompletedProcess with returncode, stdout, stderr

    Example:
        result = await run_shell_async('kubectl get pods | grep Running')
    """
    logger.debug(f"Running async shell command: {command}")

    try:
        # Create subprocess with pipes if capturing output
        if capture_output:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                env=env,
            )

        # Wait for completion with optional timeout
        try:
            if timeout:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate()
        except TimeoutError:
            # Kill the process on timeout
            process.kill()
            await process.wait()
            logger.error(f"Shell command timed out after {timeout}s: {command}")
            raise

        # Decode output
        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

        # Create result
        result = AsyncCompletedProcess(
            args=command, returncode=process.returncode or 0, stdout=stdout, stderr=stderr
        )

        # Check for errors if requested
        if check and result.returncode != 0:
            import subprocess

            raise subprocess.CalledProcessError(
                returncode=result.returncode,
                cmd=command,
                output=stdout,
                stderr=stderr,
            )

        logger.debug(
            f"Shell command completed: returncode={result.returncode}, "
            f"stdout_len={len(stdout)}, stderr_len={len(stderr)}"
        )

        return result

    except Exception as e:
        logger.error(f"Error running shell command: {e}")
        raise
