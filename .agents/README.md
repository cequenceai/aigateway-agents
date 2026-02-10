# Agent Scratchpad

Shared communication system for multiple AI agents working on this project.

## Purpose

This allows multiple AI agents (Claude, GPT, etc.) to:
- **Communicate** - Leave notes and messages for each other
- **Share Resources** - Share file paths, data, configurations
- **Coordinate Tasks** - Track and assign tasks
- **Track State** - Share state information
- **Avoid Duplication** - Know what others are working on

## File Structure

- `scratchpad.json` - Main shared data file (JSON format)
- `.lock` - Lock file for concurrent access (auto-managed)

## Usage

### Python API

```python
from agent_scratchpad import AgentScratchpad

# Initialize with your agent name
scratchpad = AgentScratchpad(agent_name="claude")

# Leave a note for other agents
scratchpad.leave_note(
    "I've cleaned up the test files. See deprecated/ folder.",
    priority="normal",
    tags=["cleanup", "tests"]
)

# Read notes from other agents
notes = scratchpad.read_notes(unread_only=True)
for note in notes:
    print(f"From {note['agent']}: {note['message']}")
    scratchpad.mark_note_read(note['id'])

# Share a resource
scratchpad.share_resource(
    key="test_results",
    value="/path/to/results.json",
    description="Latest test results"
)

# Get a shared resource
results_path = scratchpad.get_resource("test_results")

# Add a task
task_id = scratchpad.add_task(
    "Refactor authentication code",
    status="pending"
)

# Update a task
scratchpad.update_task(task_id, status="in_progress", assigned_to="claude")

# Set/get state
scratchpad.set_state("current_phase", "testing")
phase = scratchpad.get_state("current_phase")
```

### Command Line

```bash
# Leave a note
python agent_scratchpad.py --agent claude --note "Working on authentication"

# Read unread notes
python agent_scratchpad.py --agent claude --read-notes

# Share a resource
python agent_scratchpad.py --agent claude --share "api_key_path" "/path/to/key"

# Get a resource
python agent_scratchpad.py --agent claude --get "api_key_path"

# List all resources
python agent_scratchpad.py --agent claude --list-resources

# Add a task
python agent_scratchpad.py --agent claude --task "Fix OAuth flow"

# List tasks
python agent_scratchpad.py --agent claude --list-tasks

# Get summary
python agent_scratchpad.py --agent claude --summary
```

## Protocol

### Notes
- **Priority levels**: `low`, `normal`, `high`, `urgent`
- **Tags**: Use tags for categorization (e.g., `["bug", "auth"]`)
- **Read status**: Notes are marked as read when accessed

### Resources
- **Keys**: Use descriptive keys (e.g., `"test_results"`, `"api_config"`)
- **Values**: Can be any JSON-serializable value
- **Access tracking**: Resources track who accessed them and when

### Tasks
- **Status**: `pending`, `in_progress`, `completed`, `cancelled`
- **Assignment**: Tasks can be assigned to specific agents
- **Metadata**: Additional task information in metadata dict

### State
- **Global state**: Shared key-value store
- **Last writer wins**: State updates overwrite previous values
- **Tracking**: State tracks who set it and when

## Best Practices

1. **Always identify yourself** - Use a consistent agent name
2. **Check before starting** - Read notes and tasks before beginning work
3. **Update tasks** - Mark tasks as in_progress when you start, completed when done
4. **Share important findings** - Use notes to share discoveries
5. **Use resources for data** - Share file paths, configs, etc. as resources
6. **Clean up** - Mark notes as read, update task status

## Example Workflow

```python
# Agent 1: Starting work
scratchpad = AgentScratchpad("agent1")
scratchpad.leave_note("Starting authentication refactor", priority="normal")
task_id = scratchpad.add_task("Refactor auth.py", status="in_progress")
scratchpad.set_state("current_work", "authentication")

# Agent 2: Checking what's happening
scratchpad = AgentScratchpad("agent2")
notes = scratchpad.read_notes()
tasks = scratchpad.get_tasks(status="in_progress")
current_work = scratchpad.get_state("current_work")

# Agent 2: Sharing findings
scratchpad.leave_note(
    "Found bug in OAuth callback handler - see line 234 in auth.py",
    priority="high",
    tags=["bug", "oauth"]
)

# Agent 1: Reading feedback
notes = scratchpad.read_notes(tags=["bug"])
# ... fixes bug ...
scratchpad.update_task(task_id, status="completed")
```

## File Format

The `scratchpad.json` file has this structure:

```json
{
  "version": "1.0",
  "last_updated": "2024-01-07T10:30:00",
  "agents": {
    "claude": {
      "first_seen": "2024-01-07T10:00:00",
      "last_seen": "2024-01-07T10:30:00",
      "note_count": 5
    }
  },
  "shared_resources": {
    "test_results": {
      "key": "test_results",
      "value": "/path/to/results.json",
      "description": "Latest test results",
      "shared_by": "claude",
      "timestamp": "2024-01-07T10:15:00",
      "access_count": 3
    }
  },
  "tasks": [
    {
      "id": 1,
      "task": "Refactor authentication",
      "status": "in_progress",
      "created_by": "claude",
      "created_at": "2024-01-07T10:00:00",
      "updated_at": "2024-01-07T10:20:00",
      "metadata": {}
    }
  ],
  "notes": [
    {
      "id": 1,
      "agent": "claude",
      "timestamp": "2024-01-07T10:00:00",
      "message": "Starting authentication refactor",
      "priority": "normal",
      "tags": [],
      "read": false
    }
  ],
  "state": {
    "current_work": {
      "value": "authentication",
      "set_by": "agent1",
      "timestamp": "2024-01-07T10:00:00"
    }
  }
}
```
