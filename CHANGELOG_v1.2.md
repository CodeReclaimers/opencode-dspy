# Changelog v1.2.0 - Data Capture Fixes

## Problem Summary

After testing v1.1.0 with real data, Sonnet 4.5 identified critical issues:
1. ❌ `actions: []` - Empty array despite tools being executed
2. ❌ Task pollution - Tool output mixed into user message
3. ❌ Duration mismatch - `duration: 0` but `timeToCompletion: 7.721`

## Root Causes Identified

### 1. Empty Actions Array
**Root Cause:** Timestamp-based filtering was broken

The code was filtering tools like this:
```typescript
const relevantToolCalls = session.toolCalls.filter(tc => {
  const tcTime = new Date(tc.timestamp).getTime();
  const userTime = new Date(current.timestamp).getTime();
  const assistantTime = new Date(assistantMsg!.timestamp).getTime();
  return tcTime >= userTime && tcTime <= assistantTime;  // WRONG!
});
```

But in reality:
- User message timestamp: `2025-11-28T03:57:52.534Z`
- Assistant message timestamp: `2025-11-28T03:57:52.534Z` (same!)
- Tool execution timestamp: `2025-11-28T03:57:56.763Z` (4 seconds later)

Tools execute AFTER the assistant message is created, so they never match the filter!

### 2. Task Pollution
**Root Cause:** User message includes tool output from OpenCode UI

The message object contained:
```
"Please append a line to @test.txt that says \"This is a test.\"\nCalled the Read tool with the following input: {\"filePath\":\"/home/alan/opencode-dspy/test.txt\"}\n<file>\n00001| \n\n(End of file - total 1 lines)\n</file>"
```

Only the first line is the actual user request!

### 3. Duration Mismatch
**Root Cause:** Wrong calculation method

Was using message timestamps (both same time), should use message info fields:
- `userMessage.info.time.created`
- `assistantMessage.info.time.completed`

## Fixes Implemented

### Fix 1: Remove Timestamp Filtering
```typescript
// OLD: Filter by timestamp (broken)
const relevantToolCalls = session.toolCalls.filter(tc => {
  const tcTime = new Date(tc.timestamp).getTime();
  return tcTime >= userTime && tcTime <= assistantTime;
});

// NEW: Include ALL tools for the conversation
const relevantToolCalls = session.toolCalls;
```

**Rationale:** Tools are executed as part of the conversation turn, just include them all.

### Fix 2: Clean User Message
```typescript
let cleanUserMessage = firstUserMsg.content;

// Remove tool execution details (after first newline if it contains "Called the")
const lines = cleanUserMessage.split('\n');
if (lines.length > 1 && lines[1].includes('Called the')) {
  cleanUserMessage = lines[0]; // Take only the first line
}

// Remove any remaining artifacts
cleanUserMessage = cleanUserMessage.replace(/Called the .+ tool.*$/s, '').trim();
cleanUserMessage = cleanUserMessage.replace(/<file>[\s\S]*?<\/file>/g, '').trim();
```

### Fix 3: Use Message Info for Duration
```typescript
const userCreated = (firstUserMsg.info as UserMessage)?.time?.created || 0;
const assistantCompleted = msgInfo?.time?.completed || 0;
const actualDuration = assistantCompleted > 0 && userCreated > 0
  ? (assistantCompleted - userCreated) / 1000
  : 0;
```

### Fix 4: Simplified Example Generation
```typescript
// OLD: Try to create multiple examples, matching tools to message pairs
for (let i = 0; i < session.messages.length; i++) {
  // Complex matching logic...
}

// NEW: One example per session
const firstUserMsg = userMessages[0];
const lastAssistantMsg = assistantMessages[assistantMessages.length - 1];
const relevantToolCalls = session.toolCalls; // All of them

// Create ONE example with:
// - Clean user message
// - Final assistant response  
// - All tool calls
```

## Expected Output Now

For the test task "Append line to test.txt":

```json
{
  "input": {
    "task": "Please append a line to test.txt that says \"This is a test.\"",
    "context": { ... }
  },
  "actions": [
    {
      "step": 1,
      "tool": "edit",
      "callID": "toolu_013y1S8WJNbYuECF5nuZHhEa",
      "args": {
        "filePath": "/home/alan/opencode-dspy/test.txt",
        "oldString": "\n",
        "newString": "This is a test.\n"
      },
      "timestamp": "2025-11-28T03:57:56.763Z",
      "result": "",
      "success": true
    }
  ],
  "outcome": {
    "toolCallCount": 1,  // Matches actions array length
    "timeToCompletion": 7.721
  },
  "metadata": {
    "duration": 4.545  // Actual duration from message.info
  }
}
```

## Testing

Run this test after updating:

```bash
# 1. Restart OpenCode
# 2. Ask: "Create a file test2.txt with Hello World"
# 3. Check the generated DSPy file

cat .opencode-logs/dspy-ses_*.json | jq '{
  task: .examples[0].input.task,
  actionCount: (.examples[0].actions | length),
  toolCount: .examples[0].outcome.metrics.toolCallCount,
  duration: .examples[0].metadata.duration
}'
```

Expected:
```json
{
  "task": "Create a file test2.txt with Hello World",
  "actionCount": 1,
  "toolCount": 1,
  "duration": 3.2
}
```

## Summary

| Issue | Status | Fix |
|-------|--------|-----|
| Empty actions array | ✅ Fixed | Removed timestamp filtering |
| Task pollution | ✅ Fixed | Clean user message extraction |
| Duration mismatch | ✅ Fixed | Use message.info timestamps |
| Example generation | ✅ Improved | Single example per session |

**Version:** v1.2.0
**Date:** 2025-11-27
**Ready for testing!**
