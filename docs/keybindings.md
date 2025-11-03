# Butler Keyboard Shortcuts

## Overview

Butler's interactive mode supports keyboard shortcuts (keybindings) that enhance productivity by providing quick access to common actions without needing to type commands. These shortcuts are powered by an extensible keybinding system built on `prompt_toolkit`.

## Available Keybindings

### ESC - Clear Prompt

**Trigger:** Press `ESC` key

**Action:** Clears the current prompt text

**Use case:** Quickly clear the input when you change your mind about a query or want to start over without manually deleting all text.

**Example:**
```
> create a cluster called very-long-name-that-I-changed-my-mind-about
[Press ESC]
>
```

### ! - Execute Shell Command

**Trigger:** Type `!` followed by a shell command

**Action:** Executes the command directly in your shell and displays the output inline

**Use case:** Run system commands without leaving Butler's interactive session. Perfect for checking system state, listing files, or running diagnostics while working with clusters.

**Example:**
```
> !ls -la
$ ls -la
total 24
drwxr-xr-x  5 user  staff   160 Jan  3 10:30 .
drwxr-xr-x 10 user  staff   320 Jan  3 10:25 ..
-rw-r--r--  1 user  staff  1234 Jan  3 10:30 README.md
...

Exit code: 0

>
```

## Shell Command Usage

### Basic Shell Commands

Execute any shell command by prefixing it with `!`:

```bash
# List files
> !ls

# Check current directory
> !pwd

# Show git status
> !git status

# View environment variables
> !env | grep BUTLER
```

### Docker Commands

Quickly check Docker containers and images:

```bash
# List running containers
> !docker ps

# List all containers
> !docker ps -a

# View images
> !docker images

# Check Docker disk usage
> !docker system df
```

### Kubernetes Commands

Run kubectl commands alongside Butler's cluster management:

```bash
# List pods in all namespaces
> !kubectl get pods -A

# Check cluster nodes
> !kubectl get nodes

# View cluster info
> !kubectl cluster-info

# Check current context
> !kubectl config current-context
```

### Complex Commands

Shell commands support pipes, redirects, and other shell features:

```bash
# Find and filter
> !ps aux | grep docker

# Count files
> !ls -1 | wc -l

# Check disk usage
> !df -h | grep /dev/disk

# Search logs
> !tail -100 /var/log/system.log | grep error
```

## Mixed AI and Shell Workflows

Combine Butler's AI capabilities with direct shell commands for powerful workflows:

### Example 1: Cluster Creation and Verification

```
> create a cluster called dev-test
✓ Cluster created successfully

> !docker ps
[Shows the KinD container running]

> !kubectl get nodes --context kind-dev-test
[Shows cluster nodes]

> status of dev-test
[Butler provides detailed cluster status]
```

### Example 2: Debugging Applications

```
> create a cluster called app-debug

> !kubectl apply -f my-app.yaml --context kind-app-debug
[Deploys application]

> !kubectl get pods --context kind-app-debug
[Shows pod status]

> !kubectl logs my-app-pod --context kind-app-debug
[Shows application logs]
```

### Example 3: File System Navigation

```
> !pwd
/Users/yourname/projects/butler-agent

> !ls data/infra/
kind-config.yaml
kind-production.yaml

> create a cluster using production config
[Butler uses the file you just saw]
```

## Output Formatting

Shell command output is clearly formatted:

- **Command echo:** Shows the executed command with `$` prefix
- **Standard output:** Displayed in default terminal color
- **Standard error:** Displayed in red for visibility
- **Exit code:** Shown at the end
  - Green for success (0)
  - Yellow for timeout (124)
  - Red for errors (non-zero)

Example with error:
```
> !nonexistent-command
$ nonexistent-command
command not found: nonexistent-command

Exit code: 127
```

## Session Management

### Auto-Save on Exit

Butler automatically saves your session whenever you exit, so you never lose work:

```bash
> create a cluster called dev
> get status of dev
> quit
✓ Session auto-saved
Run 'butler --continue' to resume.
```

Sessions are saved in `~/.butler/conversations/` with automatic timestamps.

### Resume Last Session

Resume where you left off with the `--continue` flag:

```bash
$ butler --continue
✓ Resumed session 'auto-2025-01-03-14-30' (8 messages)

> # Continue your work
> delete cluster dev
```

### Switch Sessions

Use `/continue` in interactive mode to pick from all saved sessions:

```bash
> /continue

Available Sessions:
  1. auto-2025-01-03-14-30 (5m ago) "create a cluster called dev..."
  2. auto-2025-01-03-13-15 (2h ago) "kubectl get pods in staging..."
  3. auto-2025-01-02-16-45 (1d ago) "deploy nginx to production..."

Select session [1-3]: 2
✓ Loaded 'auto-2025-01-03-13-15' (12 messages)

> # Now working in the selected session
```

### Clean Up Old Sessions

Use `/purge` to delete all saved sessions:

```bash
> /purge
⚠ This will delete ALL 15 saved sessions. Continue? (y/n): y
✓ Deleted 15 sessions
```

### Session Workflow Examples

**Multi-day projects:**
```bash
# Day 1
$ butler
> create and configure dev cluster
> quit
✓ Session auto-saved

# Day 2
$ butler --continue
> # Continue from yesterday
> deploy application to dev
```

**Context switching:**
```bash
> working on feature A
> /continue        # Switch to different context
  1. auto-...  "feature A work..."
  2. auto-...  "hotfix for production..."
Select: 2
> # Work on hotfix
> quit

$ butler --continue   # Returns to hotfix (most recent)
```

**Quick shell access:**
```bash
> create cluster test
> !kubectl get pods --context kind-test
> analyze the output
> quit
✓ Session auto-saved
```

## Safety and Limitations

### Security

- **User permissions:** Commands run with your user permissions (no privilege escalation)
- **Working directory:** Commands execute in Butler's current working directory
- **No injection risk:** Only commands you type directly are executed
- **Shell features:** Full shell support (pipes, redirects, environment variables)

### Limitations

1. **Timeout:** Commands timeout after 30 seconds by default
2. **Interactive commands:** Commands requiring user input will timeout
3. **No background jobs:** Commands run synchronously (no `&` for background)
4. **Large output:** Very large outputs may slow the terminal
5. **No history separation:** Shell commands use Butler's history (not shell history)

### Best Practices

**DO:**
- ✅ Use for quick system checks (`!ls`, `!docker ps`)
- ✅ Combine with Butler queries for context
- ✅ Use for non-destructive operations
- ✅ Check exit codes for command success

**DON'T:**
- ❌ Run long-running commands (will timeout)
- ❌ Run commands requiring user input
- ❌ Use for destructive operations without care
- ❌ Rely on it for production scripts

## Troubleshooting

### Command Not Found

```
> !mycommand
$ mycommand
command not found: mycommand

Exit code: 127
```

**Solution:** Ensure the command is installed and in your PATH.

### Command Timeout

```
> !sleep 100
$ sleep 100
Command timed out after 30s

Exit code: 124
```

**Solution:** Use shorter commands or run long operations outside Butler.

### Permission Denied

```
> !cat /etc/shadow
$ cat /etc/shadow
cat: /etc/shadow: Permission denied

Exit code: 1
```

**Solution:** Run Butler with appropriate permissions or use `sudo` if needed.

### Empty Output

Some commands produce no output on success:

```
> !mkdir test-dir
$ mkdir test-dir

Exit code: 0
```

This is expected - check the exit code to confirm success.

## Architecture

The keybinding system is built using a modular, extensible architecture:

- **KeybindingHandler:** Base class defining the interface for all handlers
- **KeybindingManager:** Central registry for registering and managing handlers
- **Concrete Handlers:**
  - `ClearPromptHandler` - ESC key functionality
  - `ShellCommandHandler` - ! key functionality

This architecture makes it easy to add new keybindings in the future. See [CONTRIBUTING.md](../CONTRIBUTING.md) for details on adding custom keybindings.

## Related Documentation

- [Usage Guide](../USAGE.md) - General Butler usage
- [README](../README.md) - Project overview
- [CLI Documentation](../README.md#usage) - Command-line interface details

## Feedback

Found a bug or have a suggestion for keybindings? Please [open an issue](https://github.com/danielscholl/butler-agent/issues) on GitHub.
