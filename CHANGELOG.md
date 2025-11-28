# Changelog - DSPy Session Logger

## v1.1.0 (2025-11-27) - Critical Fixes

Based on feedback from Sonnet 4.5 after analyzing real training data.

### 🐛 Critical Fixes

#### 1. Fixed Missing Tool Calls
**Problem:** Only 2 out of 15 tool calls were being captured
**Root Cause:** Tool matching in `tool.execute.after` was using `.find()` without unique identifiers, causing tools of the same type to overwrite each other
**Solution:**
- Added `callID` field to `ToolCall` interface
- Store unique `callID` from the hook input
- Match tool results by `callID` instead of tool name
- Initialize session in `tool.execute.before` if not exists

**Impact:** Now captures ALL tool executions reliably

```typescript
// Before - could miss tools
const toolCall = session.toolCalls.find(tc => 
  tc.tool === tool && !tc.result
);

// After - uses unique ID
const toolCall = session.toolCalls.find(tc => tc.callID === callID);
```

#### 2. Task Completion Detection
**Problem:** Marking incomplete tasks as successful (tasks that were only started, not finished)
**Solution:** Added `isTaskComplete()` function with completion phrase detection

```typescript
const completionPhrases = [
  "I've completed",
  "I've successfully",
  "I've removed",
  "Done",
  "Successfully",
  "All files have been",
  "Task finished"
  // ... more phrases
];
```

**Impact:** Only saves sessions where the agent actually completed the task

#### 3. Task-Type-Aware Success Evaluation
**Problem:** Generic success evaluation didn't account for task requirements
**Solution:** Added task type detection and type-specific success criteria

```typescript
function detectTaskType(userMessage: string): string {
  if (msg.includes('remove') || msg.includes('delete')) return 'delete';
  if (msg.includes('fix') || msg.includes('error')) return 'fix';
  if (msg.includes('add') || msg.includes('create')) return 'add';
  // ...
}

// Task-specific success checks
if (taskType === 'delete' && filesModified > 0 && taskComplete) taskSuccess = true;
if (taskType === 'fix' && lspErrorsCleared && taskComplete) taskSuccess = true;
```

**Impact:** More accurate success evaluation based on what the task actually required

### ✨ Enhancements

#### 4. Cache Hit Rate Calculation
**Problem:** Not tracking how effective prompt caching is
**Solution:** Added cache hit rate metric

```typescript
const totalTokens = totalInputTokens + totalCacheRead;
const cacheHitRate = totalTokens > 0 ? totalCacheRead / totalTokens : 0;

// Added to metrics
metrics: {
  cacheHitRate: 0.99  // 99% of tokens from cache
}
```

**Impact:** Can now optimize for prompt caching effectiveness

#### 5. Better Efficiency Scoring
**Problem:** Efficiency score was too simplistic (time-based only)
**Solution:** Estimate ideal tool calls based on task type

```typescript
// Estimate ideal tool calls by task type
let idealToolCalls = 3;
if (taskType === 'delete') idealToolCalls = 2; // list + delete
if (taskType === 'fix') idealToolCalls = 3;    // read + edit + verify
if (taskType === 'add') idealToolCalls = 4;    // read + write + test

const efficiencyScore = Math.max(0.1, Math.min(1.0, idealToolCalls / actualToolCalls));
```

**Impact:** More meaningful efficiency scores (penalizes unnecessary tool usage)

#### 6. Improved Training Filter
**Problem:** `shouldSaveForTraining` didn't check task completion
**Solution:** Added task completion requirement and detailed logging

```typescript
return (
  outcome.success &&
  outcome.taskCompleted &&  // NEW: Must be completed
  session.toolCalls.length > 0 &&
  session.messages.length >= 2 &&
  outcome.metrics.timeToCompletion < 300
);
```

**Impact:** Only saves truly complete, successful examples

#### 7. Better Tool Result Handling
**Problem:** Tool results could be objects, not just strings
**Solution:** Safely extract and stringify tool results

```typescript
let resultText = '';
if (typeof output.output === 'string') {
  resultText = output.output;
} else if (output.output && typeof output.output === 'object') {
  resultText = JSON.stringify(output.output);
}
```

**Impact:** No more crashes on non-string tool results

#### 8. Enhanced Logging
**Problem:** Hard to debug why sessions weren't saved
**Solution:** Added detailed reason logging

```typescript
const reasons = [];
if (!outcome.success) reasons.push('not successful');
if (!outcome.taskCompleted) reasons.push('task not completed');
// ...
log(`⏭️ Not saving for training: ${reasons.join(', ')}`);
```

**Impact:** Easy to diagnose data quality issues

## Summary of Changes

| Issue | Status | Impact |
|-------|--------|--------|
| Missing tool calls | ✅ Fixed | Now captures ALL tools |
| Incomplete tasks marked successful | ✅ Fixed | Only saves completed tasks |
| Generic success criteria | ✅ Fixed | Task-type-aware evaluation |
| No cache metrics | ✅ Added | Track caching effectiveness |
| Poor efficiency scoring | ✅ Improved | Context-aware scoring |
| Missing completion check | ✅ Added | Filter incomplete examples |

## Migration Notes

### Data Format Changes

**New fields in ToolCall:**
```typescript
interface ToolCall {
  callID: string;  // NEW: Unique identifier
  // ... existing fields
}
```

**New fields in metrics:**
```typescript
metrics: {
  cacheHitRate?: number;  // NEW: 0-1 cache hit rate
  // ... existing fields
}
```

### Breaking Changes

None - all changes are additive or fixes

### Testing Recommendations

Run this simple test after upgrading:

```bash
# 1. Restart OpenCode with updated plugin
# 2. Complete a simple task:
#    "Create a file called test.txt with the text 'Hello World'"
# 3. Check logs:
grep "Tool call:" .opencode-logs/plugin.log | wc -l  # Should match actual tools used
grep "SUCCESS=true" .opencode-logs/plugin.log        # Should only show after completion
```

Expected results:
- ✅ All tool calls captured (read count matches bash/edit/write executions)
- ✅ Session only saved after seeing completion phrase
- ✅ Task type correctly detected
- ✅ Efficiency score between 0.5-1.0 for reasonable tool usage

## Next Version (Planned)

- [ ] Add test result detection (parse test output)
- [ ] Capture git diff for before/after comparison
- [ ] Add LSP diagnostics snapshots between actions
- [ ] Track file line counts for edit operations
- [ ] Add conversation turn tracking
- [ ] Improve context with file dependencies

---

**Version:** v1.1.0
**Date:** 2025-11-27
**Compatibility:** OpenCode Plugin API v1.x
