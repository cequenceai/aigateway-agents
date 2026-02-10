# Agent Scratchpad - Quick Reference

## Most Common Commands

```python
from agent_scratchpad import AgentScratchpad
scratchpad = AgentScratchpad("your_agent_name")
```

### Before Starting Work
```python
# Check what others are doing
notes = scratchpad.read_notes()
tasks = scratchpad.get_tasks(status="in_progress")
summary = scratchpad.get_summary()
```

### Announce Your Work
```python
scratchpad.leave_note("Starting work on X")
task_id = scratchpad.add_task("Do X", status="in_progress")
```

### Share Something
```python
scratchpad.share_resource("key", "value", "description")
value = scratchpad.get_resource("key")
```

### When Done
```python
scratchpad.update_task(task_id, status="completed")
scratchpad.leave_note("Work on X complete")
```

## CLI Quick Commands

```bash
# Leave note
python agent_scratchpad.py --agent NAME --note "message"

# Read notes
python agent_scratchpad.py --agent NAME --read-notes

# Share resource
python agent_scratchpad.py --agent NAME --share KEY VALUE

# Get resource
python agent_scratchpad.py --agent NAME --get KEY

# Summary
python agent_scratchpad.py --agent NAME --summary
```

## Priority Levels
- `urgent` - Immediate attention needed
- `high` - Important
- `normal` - Standard (default)
- `low` - FYI

## Task Status
- `pending` - Not started
- `in_progress` - Currently working
- `completed` - Done
- `cancelled` - Won't do
