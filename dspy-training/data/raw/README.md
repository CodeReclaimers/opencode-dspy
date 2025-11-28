# Raw Session Logs

Place your OpenCode session log JSON files in this directory.

## File Format

Each JSON file should contain a complete session log with the following structure:

```json
{
  "session": "unique-session-id",
  "generated": "2024-01-01T00:00:00Z",
  "totalExamples": 1,
  "outcome": {
    "success": true,
    "taskCompleted": true,
    "metrics": {},
    "evaluation": {}
  },
  "examples": [
    {
      "input": {
        "task": "Description of the coding task",
        "context": {}
      },
      "actions": [
        {
          "step": 1,
          "tool": "tool_name",
          "args": {},
          "timestamp": "2024-01-01T00:00:00Z",
          "result": "...",
          "success": true
        }
      ],
      "output": {
        "response": "Response from the agent"
      },
      "outcome": {
        "success": true,
        "taskCompleted": true,
        "metrics": {}
      },
      "agent": {},
      "metadata": {}
    }
  ]
}
```

## Getting Session Logs

See the main README.md for instructions on collecting session logs from OpenCode.

## Validation

Before training, validate your data with:

```bash
make prepare-data
```
