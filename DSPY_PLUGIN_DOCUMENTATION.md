# DSPy-Enhanced Session Logger Plugin

## Overview

This plugin has been completely rebuilt to capture **comprehensive training data** for DSPy optimization. It now tracks all the critical information needed for effective machine learning on coding tasks.

## Key Enhancements

### 1. **Complete Tool Call Tracking** ✅

Every tool/action is now logged with full details:

```typescript
interface ToolCall {
  step: number;              // Sequential step number
  tool: string;              // Tool name (read, edit, write, bash, etc.)
  args: any;                 // Full arguments passed to the tool
  result?: any;              // Tool output/result
  success?: boolean;         // Whether the tool call succeeded
  timestamp: string;         // When it was executed
  lspDiagnosticsAfter?: LspDiagnostics;  // LSP state after execution
}
```

**Captured via hooks:**
- `tool.execute.before` - Captures args before execution
- `tool.execute.after` - Captures results after execution

### 2. **Rich Project Context** ✅

Each example includes comprehensive project state:

```typescript
interface ProjectContext {
  workingDirectory: string;
  projectType?: string;      // 'javascript', 'typescript', etc.
  relevantFiles: string[];   // List of key project files
  lspDiagnostics?: {         // Current LSP error/warning state
    errors: Array<{
      file: string;
      line: number;
      message: string;
      severity: string;
    }>;
    warnings: Array<...>;
  };
  gitStatus?: {              // Git repository state
    branch: string;
    uncommittedChanges: number;
    status?: string;
  };
  fileCount?: number;
}
```

**Collected via:**
- File system scanning for relevant files
- Git CLI commands for repository status
- Stored at session start and refresh

### 3. **Comprehensive Outcome Evaluation** ✅

Each session is evaluated for success and quality:

```typescript
interface OutcomeMetrics {
  success: boolean;          // Overall task success
  taskCompleted: boolean;    // Was the task completed?
  metrics: {
    compilationSuccess?: boolean;
    testsPass?: boolean;
    lspErrorsCleared?: boolean;  // Did we fix LSP errors?
    filesModified: number;       // How many files changed?
    linesChanged?: number;
    timeToCompletion: number;    // Duration in seconds
    toolCallCount: number;       // Number of tools used
    tokenCost: {                 // LLM API costs
      input: number;
      output: number;
      cache?: { read: number; write: number; };
    };
  };
  evaluation?: {             // Quality scores (0-1)
    correctness: number;     // Did it solve the problem?
    efficiency: number;      // How fast was it?
    minimalEdits?: number;   // Did it make minimal changes?
  };
}
```

**Success criteria:**
- ✅ No errors in final assistant message
- ✅ At least one tool call was made
- ✅ Conversation has meaningful content (≥2 messages)
- ✅ Message finished properly (not aborted)
- ✅ Completed in reasonable time (<5 minutes)

### 4. **Intelligent Training Data Filtering** ✅

Only successful, high-quality examples are saved:

```typescript
const shouldSaveForTraining = (session: SessionData, outcome: OutcomeMetrics): boolean => {
  return (
    outcome.success &&                     // Task succeeded
    session.toolCalls.length > 0 &&        // Agent took actions
    session.messages.length >= 2 &&        // Has user input and response
    outcome.metrics.timeToCompletion < 300 // Completed in reasonable time
  );
}
```

**This ensures DSPy only learns from:**
- ✅ Successfully completed tasks
- ✅ Sessions with actual tool usage
- ✅ Real conversations (not errors/failures)
- ✅ Efficient completions

### 5. **Agent/Model Metadata** ✅

Tracks which agent and model produced each result:

```typescript
interface AgentInfo {
  name?: string;             // Agent name (e.g., "build", "general")
  model: string;             // Full model ID (e.g., "anthropic/claude-sonnet-4-5")
  temperature?: number;      // Model temperature setting
  promptTokens: number;      // Input tokens used
  completionTokens: number;  // Output tokens generated
}
```

### 6. **Conversation Context** ✅

Each example includes conversation history:

```typescript
{
  input: {
    task: "Fix the TypeScript compilation error",
    context: { /* project context */ },
    conversationHistory: [
      {
        role: "user",
        content: "The build is failing",
        timestamp: "2025-11-27T10:00:00.000Z"
      },
      {
        role: "assistant",
        content: "Let me check the error...",
        timestamp: "2025-11-27T10:00:05.000Z"
      }
      // Up to 6 previous messages for context
    ]
  }
}
```

## Output Format

### DSPy Training Examples

Each session produces a JSON file with this structure:

```json
{
  "session": "ses_537ea66faffeYxAR3KEJFwjNze",
  "generated": "2025-11-28T03:14:10.848Z",
  "totalExamples": 3,
  "outcome": {
    "success": true,
    "taskCompleted": true,
    "metrics": { ... },
    "evaluation": { ... }
  },
  "examples": [
    {
      "input": {
        "task": "User's request text",
        "context": { /* ProjectContext */ },
        "conversationHistory": [ /* Previous messages */ ]
      },
      "actions": [
        {
          "step": 1,
          "tool": "read",
          "args": { "filePath": "..." },
          "result": "...",
          "success": true,
          "timestamp": "..."
        },
        {
          "step": 2,
          "tool": "edit",
          "args": { ... },
          "result": "...",
          "success": true,
          "timestamp": "..."
        }
      ],
      "output": {
        "response": "Assistant's response text",
        "finalMessage": "msg_id"
      },
      "outcome": { /* OutcomeMetrics */ },
      "agent": { /* AgentInfo */ },
      "metadata": {
        "timestamp": "...",
        "sessionId": "...",
        "duration": 45.2,
        "messageCount": 4
      }
    }
  ]
}
```

## How It Works

### Event Flow

1. **Session Start** (`message.updated` for first message)
   - Initialize session tracking
   - Collect initial project context
   - Record LSP diagnostics baseline

2. **During Conversation** (each `message.updated`)
   - Fetch and store message content
   - Track message timing

3. **Tool Execution** (`tool.execute.before/after`)
   - Capture tool name and arguments
   - Record results and success status
   - Sequence actions with step numbers

4. **Session End** (`session.idle`)
   - Collect final project context
   - Evaluate session outcome
   - **Filter:** Only save if successful
   - Generate DSPy training examples
   - Save both raw session and DSPy format

### File Outputs

The plugin creates two files per session in `.opencode-logs/`:

1. **`session-{sessionId}.json`** - Raw session data with all messages and tool calls
2. **`dspy-{sessionId}.json`** - Formatted training examples (only if successful)

### Logging

Detailed plugin activity is logged to `.opencode-logs/plugin.log`:

```
2025-11-28T03:14:10.848Z - === Plugin Initialized (DSPy Enhanced Version) ===
2025-11-28T03:14:15.123Z - 🆕 New session tracked: ses_123abc
2025-11-28T03:14:16.456Z - 🔧 Tool call: read (step 1)
2025-11-28T03:14:16.789Z - ✅ Tool result: read (success=true)
2025-11-28T03:14:20.000Z - ✅ Logged assistant message (1234 chars)
2025-11-28T03:15:00.000Z - 💾 Session idle, saving: ses_123abc
2025-11-28T03:15:00.100Z - 🔄 Generating DSPy format for session ses_123abc...
2025-11-28T03:15:00.200Z - ✅ Saved DSPy format: 2 examples (SUCCESS=true)
```

## Usage with DSPy

### Training Data Format

The output is ready for DSPy's `Example` class:

```python
from dspy import Example
import json

# Load training data
with open('.opencode-logs/dspy-ses_123abc.json') as f:
    data = json.load(f)

# Convert to DSPy examples
examples = []
for ex in data['examples']:
    examples.append(Example(
        task=ex['input']['task'],
        context=ex['input']['context'],
        actions=ex['actions'],
        response=ex['output']['response']
    ).with_inputs('task', 'context'))
```

### Filtering and Quality Control

Only use examples where `outcome.success == true`:

```python
# Filter for successful examples only
successful_examples = [
    ex for ex in data['examples']
    if data['outcome']['success'] == True
]

# Further filter by quality metrics
high_quality = [
    ex for ex in successful_examples
    if data['outcome']['evaluation']['efficiency'] > 0.7 and
       data['outcome']['evaluation']['correctness'] >= 1.0
]
```

### Training Signals

Use the rich metadata for optimization:

```python
# Examples with tool usage patterns
tool_heavy = [ex for ex in examples if len(ex['actions']) > 3]

# Examples that fixed errors
error_fixing = [
    ex for ex in examples
    if ex['outcome']['metrics']['lspErrorsCleared']
]

# Fast completions
efficient = [
    ex for ex in examples
    if ex['outcome']['metrics']['timeToCompletion'] < 60
]
```

## What Makes This DSPy-Ready

### ✅ Complete Action Traces
DSPy can learn which tools to use and when

### ✅ Rich Context
DSPy understands the environment and constraints

### ✅ Success Metrics
DSPy can optimize for actual task completion

### ✅ Quality Filtering
Only high-quality examples are saved for training

### ✅ Conversation History
DSPy can learn from multi-turn interactions

### ✅ Token Economics
DSPy can optimize for cost efficiency

## Comparison with Original Version

| Feature | Original | DSPy-Enhanced |
|---------|----------|---------------|
| Message content | ✅ | ✅ |
| Tool call tracking | ❌ | ✅ Complete with args/results |
| Project context | ❌ | ✅ Files, Git, LSP |
| Success evaluation | ❌ | ✅ Multi-factor metrics |
| Training filtering | ❌ | ✅ Only save successful |
| Agent metadata | ❌ | ✅ Model, tokens, timing |
| Conversation history | Partial | ✅ Full with timestamps |
| Outcome metrics | ❌ | ✅ Comprehensive |

## Next Steps

1. **Test the plugin** - Start OpenCode and verify logging works
2. **Generate examples** - Complete a few coding tasks
3. **Inspect output** - Check `.opencode-logs/dspy-*.json` files
4. **Train DSPy** - Use examples to optimize prompts/chains
5. **Iterate** - Adjust success criteria based on results

## Technical Notes

- Uses OpenCode's plugin hooks: `event`, `tool.execute.before`, `tool.execute.after`
- Auto-saves every 5 message updates (prevents data loss)
- Saves on `session.idle` event (conversation pause)
- Silent failures to avoid disrupting normal operation
- TypeScript with full type safety
- Minimal dependencies (fs/promises, path)

## Success Criteria Summary

A session is saved for training if:
1. ✅ No errors in final message
2. ✅ At least one tool call executed
3. ✅ Has meaningful conversation (≥2 messages)
4. ✅ Completed successfully (proper finish reason)
5. ✅ Reasonable duration (<5 minutes)

This ensures DSPy learns from **successful, efficient, real coding interactions** only.
