# OpenCode DSPy Training Data Plugin

A comprehensive session logging plugin for OpenCode that captures high-quality training data for DSPy optimization.

## 🎯 What This Does

Automatically logs your OpenCode coding sessions in a format optimized for training DSPy language models. Only saves successful interactions with complete context, tool traces, and outcome metrics.

## ✨ Key Features

- **Complete Tool Traces** - Every read, edit, write, bash command logged with args and results
- **Rich Context** - Project files, LSP diagnostics, git status captured automatically
- **Success Filtering** - Only saves successful sessions (no errors or failures)
- **Outcome Evaluation** - Metrics for correctness, efficiency, and code quality
- **Agent Metadata** - Model information, token usage, timing data
- **DSPy-Ready Format** - Output designed specifically for DSPy training

## 📁 Files

| File | Purpose |
|------|---------|
| `.opencode/plugin/session-logger.ts` | Main plugin (632 lines) |
| `QUICK_START.md` | **Start here!** Quick setup guide |
| `UPGRADE_COMPLETE.md` | Summary of all changes |
| `DSPY_PLUGIN_DOCUMENTATION.md` | Complete technical documentation |
| `DSPY_USAGE_GUIDE.md` | How to use with DSPy |
| `IMPLEMENTATION_SUMMARY.md` | Implementation details |
| `example-dspy-enhanced-output.json` | Example output format |

## 🚀 Quick Start

### 1. Install
The plugin is already at `.opencode/plugin/session-logger.ts`

### 2. Restart OpenCode
Look for: `📊 SessionLogger: Initialized (DSPy training data format)`

### 3. Use Normally
Complete coding tasks. The plugin logs everything automatically.

### 4. Check Output
```bash
ls .opencode-logs/dspy-*.json
```

## 📊 Output Format

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

## 🎓 DSPy Integration

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

See `DSPY_USAGE_GUIDE.md` for complete examples.

## ✅ Success Criteria

Sessions are saved for training ONLY if:
- ✅ Task completed successfully (no errors)
- ✅ At least one tool was used
- ✅ Has real conversation (≥2 messages)
- ✅ Completed in reasonable time (<5 minutes)

## 📈 What Gets Captured

### Per Session
- All messages (user + assistant)
- Tool call traces (complete with args/results)
- Project context (files, LSP, git)
- Success metrics
- Quality evaluation

### Per Tool Call
- Tool name
- Arguments
- Results
- Success status
- LSP diagnostics after execution
- Timestamps

### Context
- Working directory
- Project type (detected)
- Relevant source files
- Current LSP errors/warnings
- Git branch and uncommitted changes

### Metrics
- Files modified
- Time to completion
- Tool call count
- Token costs (input/output/cache)
- LSP errors cleared
- Quality scores (correctness, efficiency)

## 🔍 Monitoring

```bash
# Check plugin status
tail -f .opencode-logs/plugin.log

# Count successful sessions
ls .opencode-logs/dspy-*.json | wc -l

# View metrics
cat .opencode-logs/dspy-*.json | jq '.outcome.metrics'

# See success rate
grep "SUCCESS=" .opencode-logs/plugin.log
```

## 📚 Documentation

- **QUICK_START.md** - Get started in 5 minutes
- **UPGRADE_COMPLETE.md** - What changed and why
- **DSPY_PLUGIN_DOCUMENTATION.md** - Full technical docs
- **DSPY_USAGE_GUIDE.md** - DSPy integration examples
- **IMPLEMENTATION_SUMMARY.md** - How it works internally

## 🎯 Workflow

1. **Collect** - Use OpenCode for 1-2 weeks (aim for 50-100 examples)
2. **Filter** - Only successful examples are saved automatically
3. **Train** - Load into DSPy and optimize prompts
4. **Evaluate** - Measure improvements
5. **Iterate** - Continuously collect more data

## 🆘 Troubleshooting

**No files created?**
- Check `.opencode-logs/plugin.log`
- Ensure tasks complete successfully
- Verify plugin initialized

**Low success rate?**
- Tasks may be too complex
- Check for errors in sessions
- Review plugin.log for issues

## 🔧 Technical Details

- **Language:** TypeScript
- **Lines:** 632
- **Hooks:** `event`, `tool.execute.before`, `tool.execute.after`
- **Dependencies:** `@opencode-ai/plugin`, `@opencode-ai/sdk`
- **Output:** JSON files in `.opencode-logs/`

## 📝 Example Use Cases

- Train DSPy models on successful coding patterns
- Analyze tool usage patterns
- Optimize agent prompt templates
- Evaluate agent efficiency
- Build custom coding agents

## 🎉 Ready to Use

The plugin is production-ready and captures all information needed for DSPy optimization. Just restart OpenCode and start coding!

---

**Questions?** Check the documentation files above or review `.opencode-logs/plugin.log`

**Status:** ✅ Production Ready
**Version:** DSPy-Enhanced v1.0
**Last Updated:** 2025-11-27
