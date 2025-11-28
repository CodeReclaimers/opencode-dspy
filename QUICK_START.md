# Quick Start Guide

## 🎯 Goal
Generate high-quality training data for DSPy from your OpenCode sessions

## ✅ Setup (Done!)
The plugin is ready at `.opencode/plugin/session-logger.ts`

## 🚀 Usage (3 Steps)

### Step 1: Restart OpenCode
The plugin will auto-load. Look for this in the output:
```
📊 SessionLogger: Initialized (DSPy training data format)
```

### Step 2: Use OpenCode Normally
Complete coding tasks - the plugin logs everything automatically.

**What gets logged:**
- Every tool call (read, edit, write, bash, etc.)
- Full project context (files, LSP errors, git status)
- Success metrics and quality scores
- Agent/model information
- Conversation history

**What gets saved:**
Only successful sessions (no errors, completed tasks)

### Step 3: Check Output
```bash
# View saved training examples
ls -lh .opencode-logs/dspy-*.json

# Check activity log
tail -f .opencode-logs/plugin.log

# Count total examples
cat .opencode-logs/dspy-*.json | jq '.totalExamples' | paste -sd+ | bc
```

## 📊 Example Output

Each successful session creates a file like this:

```json
{
  "session": "ses_123abc",
  "outcome": {
    "success": true,
    "metrics": {
      "filesModified": 2,
      "timeToCompletion": 45.2,
      "toolCallCount": 5
    }
  },
  "examples": [
    {
      "input": {
        "task": "User's request",
        "context": { /* project state */ }
      },
      "actions": [
        { "tool": "read", "args": {...}, "result": "..." },
        { "tool": "edit", "args": {...}, "result": "..." }
      ],
      "output": {
        "response": "Assistant's explanation"
      }
    }
  ]
}
```

## 🎓 Use with DSPy

```python
import json
from dspy import Example

# Load examples
with open('.opencode-logs/dspy-ses_123.json') as f:
    data = json.load(f)

# Convert to DSPy format
for ex in data['examples']:
    example = Example(
        task=ex['input']['task'],
        context=ex['input']['context'],
        response=ex['output']['response']
    ).with_inputs('task', 'context')
```

## 📖 Documentation

- `UPGRADE_COMPLETE.md` - What changed and why
- `DSPY_PLUGIN_DOCUMENTATION.md` - Technical details
- `DSPY_USAGE_GUIDE.md` - DSPy integration examples
- `IMPLEMENTATION_SUMMARY.md` - How it works

## ✨ Success Criteria

Sessions are saved ONLY if:
- ✅ Task completed successfully
- ✅ No errors in final message
- ✅ At least one tool used
- ✅ Real conversation (≥2 messages)
- ✅ Completed in <5 minutes

## 🔍 Monitoring

```bash
# See success messages
grep "SUCCESS=true" .opencode-logs/plugin.log

# View recent activity
tail -20 .opencode-logs/plugin.log

# Check a specific session
cat .opencode-logs/dspy-ses_123abc.json | jq '.outcome'
```

## 🎯 Next Steps

1. **Test It** (5 min)
   - Restart OpenCode
   - Complete one simple task
   - Check if `.opencode-logs/dspy-*.json` file was created

2. **Collect Data** (This Week)
   - Use OpenCode for normal work
   - Aim for 50-100 successful examples
   - Variety of tasks

3. **Train DSPy** (Next Week)
   - Load collected examples
   - Create DSPy signature
   - Optimize and evaluate

## 🆘 Troubleshooting

**No files created?**
- Check `.opencode-logs/plugin.log` for errors
- Verify plugin loaded (look for "Initialized" message)
- Ensure you completed tasks successfully

**Files but no examples?**
- Check `outcome.success` in the files
- Sessions with errors aren't saved for training
- Complete a simple, successful task first

**Low success rate?**
- Tasks may be too complex
- Encountering errors during execution
- Check plugin.log for failure reasons

## 📞 Support

All questions answered in the documentation files above!

---

**You're all set! Start using OpenCode and collect training data automatically.** 🚀
