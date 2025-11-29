# OpenCode DSPy Integration

A comprehensive system for capturing OpenCode coding sessions and training DSPy models to optimize agent prompts.

## Overview

This project consists of two main components:

1. **Session Logger Plugin** - Captures high-quality training data from OpenCode sessions
2. **DSPy Training Pipeline** - Optimizes agent prompts using collected data

## Quick Start

### 1. Capture Training Data

The plugin at `.opencode/plugin/session-logger.ts` automatically captures your OpenCode sessions.

**Setup:**
```bash
# Plugin auto-loads on OpenCode restart
# Look for: "📊 SessionLogger: Initialized (DSPy training data format)"
```

**What Gets Captured:**
- Complete tool execution traces (read, edit, write, bash commands)
- Project context (files, LSP diagnostics, git status)
- Success metrics and quality scores
- Agent/model metadata
- Conversation history

**Output Files:**
```bash
.opencode-logs/
├── dspy-*.json        # Training data (successful sessions only)
├── session-*.json     # Raw session logs (all sessions)
└── plugin.log         # Activity log
```

### 2. Train DSPy Models

Once you've collected 50-100 successful examples:

```bash
cd dspy-training
make install           # Install dependencies
cp .env.example .env   # Add your API keys
make train             # Run optimization
```

See [`dspy-training/README.md`](dspy-training/README.md) for detailed training instructions.

## Features

### Session Logger

- **Smart Filtering** - Only saves successful sessions for training
- **Complete Tool Traces** - Every action with args and results
- **Rich Context** - Project files, LSP errors, git state
- **Quality Metrics** - Correctness, efficiency, minimal edits
- **Auto-Save** - Saves every 5 updates and on session idle

**Success Criteria:**
Sessions are saved for training ONLY if:
- ✅ Task completed successfully (no errors)
- ✅ At least one tool was used
- ✅ Has real conversation (≥2 messages)
- ✅ Completed in reasonable time (<5 minutes)

### DSPy Training

- **Flexible Data Loading** - Automatically loads session logs
- **Multiple Optimizers** - MIPROv2, COPRO, BootstrapFewShot
- **Custom Metrics** - Success rate, efficiency, correctness
- **OpenCode Integration** - Exports optimized prompts ready to use

## Project Structure

```
opencode-dspy/
├── .opencode/
│   └── plugin/
│       └── session-logger.ts          # Session capture plugin
├── .opencode-logs/                    # Generated training data
├── dspy-training/                     # DSPy optimization pipeline
│   ├── data/
│   │   └── raw/                       # Place session logs here
│   ├── src/                           # Training scripts
│   ├── outputs/
│   │   └── prompts/                   # Optimized prompts
│   ├── config.yaml                    # Training configuration
│   └── run_training.py                # Main training script
├── README.md                          # This file
├── DSPY_PLUGIN_DOCUMENTATION.md       # Detailed plugin documentation
└── example-dspy-enhanced-output.json  # Example output format
```

## Session Data Format

Each successful session creates a JSON file with this structure:

```json
{
  "session": "ses_123abc",
  "outcome": {
    "success": true,
    "metrics": {
      "filesModified": 2,
      "timeToCompletion": 45.2,
      "toolCallCount": 5,
      "tokenCost": { "input": 1842, "output": 326 }
    },
    "evaluation": {
      "correctness": 1.0,
      "efficiency": 0.89
    }
  },
  "examples": [
    {
      "input": {
        "task": "User's request",
        "context": {
          "workingDirectory": "/path",
          "projectType": "typescript",
          "relevantFiles": [...],
          "lspDiagnostics": { "errors": [...] },
          "gitStatus": { "branch": "main" }
        },
        "conversationHistory": [...]
      },
      "actions": [
        {
          "step": 1,
          "tool": "read",
          "args": { "filePath": "..." },
          "result": "...",
          "success": true
        }
      ],
      "output": {
        "response": "Assistant's explanation"
      },
      "outcome": { /* metrics */ },
      "agent": {
        "model": "anthropic/claude-sonnet-4-5",
        "promptTokens": 1842
      }
    }
  ]
}
```

See [`example-dspy-enhanced-output.json`](example-dspy-enhanced-output.json) for a complete example.

## Using DSPy with Session Data

### Basic Example

```python
import json
from dspy import Example

# Load training data
with open('.opencode-logs/dspy-ses_123.json') as f:
    data = json.load(f)

# Only use successful sessions
if data['outcome']['success']:
    for ex in data['examples']:
        example = Example(
            task=ex['input']['task'],
            context=ex['input']['context'],
            actions=ex['actions'],
            response=ex['output']['response']
        ).with_inputs('task', 'context')
```

### Training an Agent

```python
import dspy
from dspy import ChainOfThought
from dspy.teleprompt import BootstrapFewShot

# Define signature
class CodingTask(dspy.Signature):
    """Solve a coding task by analyzing context and taking actions."""
    task = dspy.InputField(desc="The coding task to complete")
    context = dspy.InputField(desc="Project context")
    response = dspy.OutputField(desc="Explanation of what was done")

# Create agent
class CodingAgent(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_solution = ChainOfThought(CodingTask)
    
    def forward(self, task, context):
        return self.generate_solution(task=task, context=context)

# Load examples and optimize
# ... (see dspy-training/ for complete pipeline)
```

For complete DSPy integration examples, see the [`dspy-training/`](dspy-training/) directory.

## Monitoring

### Check Plugin Status
```bash
tail -f .opencode-logs/plugin.log
```

### Count Successful Sessions
```bash
ls .opencode-logs/dspy-*.json | wc -l
```

### View Metrics
```bash
cat .opencode-logs/dspy-*.json | jq '.outcome.metrics'
```

### Check Success Rate
```bash
grep "SUCCESS=" .opencode-logs/plugin.log
```

## Troubleshooting

### No Training Files Created?
- Check `.opencode-logs/plugin.log` for errors
- Ensure tasks complete successfully
- Verify plugin initialized (look for "Initialized" message)

### Low Success Rate?
- Tasks may be too complex
- Check for errors in sessions
- Review plugin.log for failure reasons

### Training Issues?
See [`dspy-training/README.md`](dspy-training/README.md) troubleshooting section.

## Documentation

- **[DSPY_PLUGIN_DOCUMENTATION.md](DSPY_PLUGIN_DOCUMENTATION.md)** - Complete technical documentation for the session logger plugin
- **[dspy-training/README.md](dspy-training/README.md)** - Complete DSPy training pipeline documentation
- **[dspy-training/QUICKSTART.md](dspy-training/QUICKSTART.md)** - Quick start guide for training
- **[example-dspy-enhanced-output.json](example-dspy-enhanced-output.json)** - Example session output format

## Workflow

1. **Collect** - Use OpenCode for 1-2 weeks (aim for 50-100 examples)
2. **Filter** - Only successful examples are saved automatically
3. **Train** - Load into DSPy and optimize prompts
4. **Evaluate** - Measure improvements
5. **Iterate** - Continuously collect more data

## Best Practices

### Data Collection
- Complete 50-100 successful examples before training
- Include diverse tasks (bug fixes, features, refactoring)
- Ensure examples represent real usage patterns

### Training
- Start with light optimization mode (`auto_mode: "light"`)
- Use 20/80 train/validation split
- Monitor costs with teacher model API usage
- Validate improvements on held-out data

### Quality Control
- Only use `outcome.success === true` examples
- Filter by quality metrics (correctness ≥ 1.0, efficiency > 0.7)
- Remove outliers (very long or very short sessions)

## Technical Details

### Session Logger Plugin
- **Language:** TypeScript
- **Lines:** 632
- **Hooks:** `event`, `tool.execute.before`, `tool.execute.after`
- **Output:** JSON files in `.opencode-logs/`

### DSPy Training Pipeline
- **Language:** Python 3.8+
- **Optimizers:** MIPROv2, COPRO, BootstrapFewShot
- **Teacher Models:** Anthropic Claude, OpenAI GPT-4
- **Target Models:** Any LLM (Ollama, OpenAI, Anthropic, etc.)

## Contributing

Contributions welcome! The project is structured to make it easy to:
- Add new metrics for evaluation
- Support additional optimizers
- Enhance context collection
- Improve data quality filtering

## License

MIT License - see [LICENSE](LICENSE) file

## Community

Built for the OpenCode and DSPy communities:
- **OpenCode:** https://opencode.ai
- **DSPy:** https://github.com/stanfordnlp/dspy

## Status

✅ **Production Ready**
- Plugin captures all critical information for DSPy
- Training pipeline tested and working
- Documentation complete
- Ready for community use

## Version

- **Session Logger:** v1.2.0
- **DSPy Training:** v1.0.0
- **Last Updated:** 2025-11-28
