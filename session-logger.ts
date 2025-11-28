/**
 * OpenCode Session Logger - DSPy Training Data Format
 * 
 * Captures comprehensive session data for DSPy optimization including:
 * - Tool calls and actions taken
 * - Project context (files, LSP diagnostics, git status)
 * - Outcome evaluation and success metrics
 * - Agent/model information
 */

import type { Plugin } from "@opencode-ai/plugin";
import { writeFile, mkdir, readdir } from "fs/promises";
import { join } from "path";
import type { AssistantMessage, UserMessage } from "@opencode-ai/sdk";

// Enhanced interfaces for DSPy training data
interface ToolCall {
  step: number;
  tool: string;
  callID: string;  // Unique identifier for matching before/after
  args: any;
  result?: any;
  success?: boolean;
  timestamp: string;
  lspDiagnosticsAfter?: LspDiagnostics;
}

interface LspDiagnostics {
  errors: Array<{
    file: string;
    line: number;
    message: string;
    severity: string;
  }>;
  warnings: Array<{
    file: string;
    line: number;
    message: string;
    severity: string;
  }>;
}

interface ProjectContext {
  workingDirectory: string;
  projectType?: string;
  relevantFiles: string[];
  lspDiagnostics?: LspDiagnostics;
  gitStatus?: {
    branch: string;
    uncommittedChanges: number;
    status?: string;
  };
  fileCount?: number;
}

interface OutcomeMetrics {
  success: boolean;
  taskCompleted: boolean;
  metrics: {
    compilationSuccess?: boolean;
    testsPass?: boolean;
    lspErrorsCleared?: boolean;
    filesModified: number;
    linesChanged?: number;
    timeToCompletion: number;
    toolCallCount: number;
    cacheHitRate?: number;
    tokenCost: {
      input: number;
      output: number;
      cache?: {
        read: number;
        write: number;
      };
    };
  };
  evaluation?: {
    correctness: number;
    efficiency: number;
    minimalEdits?: number;
  };
}

interface AgentInfo {
  name?: string;
  model: string;
  temperature?: number;
  promptTokens: number;
  completionTokens: number;
}

interface DSPyExample {
  input: {
    task: string;
    context: ProjectContext;
    conversationHistory: Array<{
      role: string;
      content: string;
      timestamp?: string;
    }>;
  };
  actions: ToolCall[];
  output: {
    response: string;
    finalMessage: string;
  };
  outcome: OutcomeMetrics;
  agent: AgentInfo;
  metadata: {
    timestamp: string;
    sessionId: string;
    duration: number;
    messageCount: number;
  };
}

interface SessionData {
  sessionId: string;
  messages: Array<{
    messageId: string;
    role: string;
    timestamp: string;
    content: string;
    info?: UserMessage | AssistantMessage;
  }>;
  toolCalls: ToolCall[];
  context?: ProjectContext;
  startTime: number;
  lastUpdateTime: number;
  updateCount?: number;
  initialLspDiagnostics?: LspDiagnostics;
}

export const SessionLogger: Plugin = async ({ directory, client, $ }) => {
  const logsDir = join(directory, ".opencode-logs");
  const sessions = new Map<string, SessionData>();
  
  // Simple file logging function
  const log = async (msg: string) => {
    try {
      await mkdir(logsDir, { recursive: true });
      const logFile = join(logsDir, "plugin.log");
      const timestamp = new Date().toISOString();
      await writeFile(logFile, `${timestamp} - ${msg}\n`, { flag: "a" });
    } catch (error) {
      // Fail silently
    }
  };
  
  // Collect project context
  const collectProjectContext = async (): Promise<ProjectContext> => {
    const context: ProjectContext = {
      workingDirectory: directory,
      relevantFiles: [],
      lspDiagnostics: {
        errors: [],
        warnings: []
      },
      fileCount: 0
    };
    
    try {
      // Get file count and list
      const files = await readdir(directory, { recursive: true });
      context.fileCount = files.length;
      context.relevantFiles = files.filter((f: any) => 
        typeof f === 'string' && 
        (f.endsWith('.ts') || f.endsWith('.js') || f.endsWith('.tsx') || f.endsWith('.jsx'))
      ).slice(0, 20); // Limit to 20 most relevant files
      
      // Try to detect project type
      if (files.some((f: any) => f === 'package.json')) {
        context.projectType = 'javascript';
      } else if (files.some((f: any) => f === 'tsconfig.json')) {
        context.projectType = 'typescript';
      }
      
      // Try to get git status
      try {
        const gitBranch = await $`git branch --show-current`.text();
        const gitStatus = await $`git status --porcelain`.text();
        const uncommittedCount = gitStatus.split('\n').filter(line => line.trim()).length;
        
        context.gitStatus = {
          branch: gitBranch.trim(),
          uncommittedChanges: uncommittedCount,
          status: gitStatus
        };
      } catch (gitError) {
        // Git not available or not a repo
      }
    } catch (error) {
      await log(`⚠️ Error collecting project context: ${error}`);
    }
    
    return context;
  };
  
  // Check if task is complete based on assistant's response
  // Now checks messages within a specific range (for multi-turn conversations)
  const isTaskComplete = (assistantMessages: Array<{content: string}>): boolean => {
    if (assistantMessages.length === 0) return false;
    
    // Completion phrases that indicate the task is done
    const completionPhrases = [
      "I've completed",
      "I've successfully",
      "I've removed",
      "I've added",
      "I've fixed",
      "I've updated",
      "Done",
      "Complete",
      "Successfully",
      "All files have been",
      "Task finished",
      "Finished",
      "All set",
      "Ready to use",
      "has been fixed",
      "issue has been",
      "The fix has been"
    ];
    
    // Check ALL assistant messages in this turn for completion phrases
    return assistantMessages.some(msg => 
      completionPhrases.some(phrase => 
        msg.content.toLowerCase().includes(phrase.toLowerCase())
      )
    );
  };
  
  // Detect task type from user message
  const detectTaskType = (userMessage: string): string => {
    const msg = userMessage.toLowerCase();
    if (msg.includes('remove') || msg.includes('delete')) return 'delete';
    if (msg.includes('fix') || msg.includes('error')) return 'fix';
    if (msg.includes('add') || msg.includes('create')) return 'add';
    if (msg.includes('refactor') || msg.includes('improve')) return 'refactor';
    if (msg.includes('test')) return 'test';
    return 'general';
  };
  
  // Evaluate session outcome for a specific turn
  const evaluateOutcome = async (
    session: SessionData, 
    turnMessages: Array<{role: string, content: string, info?: any}>,
    turnToolCalls: ToolCall[]
  ): Promise<OutcomeMetrics> => {
    const assistantMessages = turnMessages.filter(m => m.role === 'assistant');
    const lastAssistantMsg = assistantMessages[assistantMessages.length - 1];
    const msgInfo = lastAssistantMsg?.info as AssistantMessage | undefined;
    
    const firstTurnMsg = turnMessages[0];
    const firstMsgTime = (firstTurnMsg?.info as any)?.time?.created || session.startTime;
    const lastMsgTime = msgInfo?.time?.completed || session.lastUpdateTime;
    const duration = (lastMsgTime - firstMsgTime) / 1000;
    
    // Calculate token costs for this turn only
    const totalInputTokens = turnMessages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.input || 0), 0);
    
    const totalOutputTokens = turnMessages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.output || 0), 0);
    
    const totalCacheRead = turnMessages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.cache?.read || 0), 0);
    
    const totalCacheWrite = turnMessages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.cache?.write || 0), 0);
    
    // Calculate cache hit rate
    const totalTokens = totalInputTokens + totalCacheRead;
    const cacheHitRate = totalTokens > 0 ? totalCacheRead / totalTokens : 0;
    
    // Count files modified from tool calls in this turn
    const filesModified = new Set(
      turnToolCalls
        .filter(tc => ['edit', 'write', 'bash'].includes(tc.tool))
        .map(tc => tc.args?.filePath || (tc.tool === 'bash' && tc.args?.command?.includes('rm') ? 'bash-delete' : null))
        .filter(Boolean)
    ).size;
    
    // Check if this turn had errors
    const hadErrors = turnMessages.some(m => 
      m.role === 'assistant' && (m.info as AssistantMessage)?.error
    );
    
    // Check if LSP errors were cleared
    const initialErrors = session.initialLspDiagnostics?.errors?.length || 0;
    const finalErrors = session.context?.lspDiagnostics?.errors?.length || 0;
    const lspErrorsCleared = initialErrors > 0 && finalErrors < initialErrors;
    
    // Get first user message in this turn to detect task type
    const firstUserMsg = turnMessages.find(m => m.role === 'user');
    const taskType = firstUserMsg ? detectTaskType(firstUserMsg.content) : 'general';
    
    // Check task completion based on type (pass only assistant messages)
    const taskComplete = isTaskComplete(assistantMessages);
    
    // Better success evaluation based on task type
    let taskSuccess = false;
    if (taskType === 'delete' && filesModified > 0 && taskComplete) {
      taskSuccess = true;
    } else if (taskType === 'fix' && lspErrorsCleared && taskComplete) {
      taskSuccess = true;
    } else if (taskType === 'add' && filesModified > 0 && taskComplete) {
      taskSuccess = true;
    } else if (taskComplete && !hadErrors) {
      taskSuccess = true;
    }
    
    // Overall success requires no errors and proper finish
    const success = taskSuccess &&
                    !hadErrors && 
                    session.toolCalls.length > 0 && 
                    session.messages.length >= 2 &&
                    (msgInfo?.finish === 'stop' || msgInfo?.finish === 'end_turn');
    
    // Better efficiency calculation
    // Estimate ideal tool calls based on task type
    let idealToolCalls = 3; // default
    if (taskType === 'delete') idealToolCalls = 2; // list + delete
    if (taskType === 'fix') idealToolCalls = 3; // read + edit + verify
    if (taskType === 'add') idealToolCalls = 4; // read + write + test
    
    const actualToolCalls = turnToolCalls.length;
    const efficiencyScore = actualToolCalls > 0 
      ? Math.max(0.1, Math.min(1.0, idealToolCalls / actualToolCalls))
      : 0.1;
    
    return {
      success,
      taskCompleted: taskComplete,
      metrics: {
        lspErrorsCleared,
        filesModified,
        timeToCompletion: duration,
        toolCallCount: turnToolCalls.length,
        tokenCost: {
          input: totalInputTokens,
          output: totalOutputTokens,
          cache: {
            read: totalCacheRead,
            write: totalCacheWrite
          }
        },
        cacheHitRate
      } as any, // Add cacheHitRate to metrics
      evaluation: {
        correctness: success ? 1.0 : (taskComplete ? 0.7 : 0.3),
        efficiency: efficiencyScore,
        minimalEdits: filesModified > 0 ? Math.min(1.0, 3 / filesModified) : 1.0
      }
    };
  };
  
  // Check if turn should be saved for training
  const shouldSaveForTraining = (
    turnMessages: Array<any>, 
    turnToolCalls: ToolCall[], 
    outcome: OutcomeMetrics,
    turnIndex: number
  ): boolean => {
    // Log reasons for not saving
    const reasons = [];
    if (!outcome.success) reasons.push('not successful');
    if (!outcome.taskCompleted) reasons.push('task not completed');
    if (turnToolCalls.length === 0) reasons.push('no tool calls');
    if (turnMessages.length < 2) reasons.push('too few messages');
    if (outcome.metrics.timeToCompletion >= 300) reasons.push('took too long');
    
    if (reasons.length > 0) {
      log(`⏭️ Turn ${turnIndex}: Not saving for training: ${reasons.join(', ')}`);
    }
    
    return (
      outcome.success &&                     // Task succeeded
      outcome.taskCompleted &&               // Task was completed (not just started)
      turnToolCalls.length > 0 &&            // Agent took actions
      turnMessages.length >= 2 &&            // Has user input and response
      outcome.metrics.timeToCompletion < 300 // Completed in reasonable time (5 min)
    );
  };
  
  // Save session in DSPy format - creates separate examples for each user turn
  const saveDSPyFormat = async (session: SessionData) => {
    try {
      await log(`🔄 Generating DSPy format for session ${session.sessionId}...`);
      
      // Collect final project context
      session.context = await collectProjectContext();
      
      const examples: DSPyExample[] = [];
      const userMessages = session.messages.filter(m => m.role === 'user');
      
      await log(`📋 Processing ${userMessages.length} user turn(s) in session`);
      
      // Process each user message as a separate turn
      for (let i = 0; i < userMessages.length; i++) {
        const userMsg = userMessages[i];
        const nextUserMsg = userMessages[i + 1];
        
        // Find user message index in full message list
        const userMsgIndex = session.messages.findIndex(m => m.messageId === userMsg.messageId);
        const nextUserMsgIndex = nextUserMsg 
          ? session.messages.findIndex(m => m.messageId === nextUserMsg.messageId)
          : session.messages.length;
        
        // Get all messages for this turn (from this user message until next user message)
        const turnMessages = session.messages.slice(userMsgIndex, nextUserMsgIndex);
        const assistantMessages = turnMessages.filter(m => m.role === 'assistant');
        
        if (assistantMessages.length === 0) {
          await log(`⏭️ Turn ${i + 1}: No assistant responses, skipping`);
          continue;
        }
        
        // Get tool calls for this turn (by timestamp range)
        const turnStart = (userMsg.info as UserMessage)?.time?.created || 0;
        const lastAssistantMsg = assistantMessages[assistantMessages.length - 1];
        const turnEnd = (lastAssistantMsg.info as AssistantMessage)?.time?.completed || Date.now();
        
        // Match tool calls by timestamp - tools executed during this turn
        const turnToolCalls = session.toolCalls.filter(tc => {
          const toolTime = new Date(tc.timestamp).getTime();
          return toolTime >= turnStart && toolTime <= turnEnd;
        });
        
        await log(`🔍 Turn ${i + 1}: ${turnMessages.length} msgs, ${turnToolCalls.length} tools`);
        
        // Evaluate outcome for this turn
        const outcome = await evaluateOutcome(session, turnMessages, turnToolCalls);
        
        // Check if we should save this turn
        if (!shouldSaveForTraining(turnMessages, turnToolCalls, outcome, i + 1)) {
          await log(`   - success: ${outcome.success}, taskComplete: ${outcome.taskCompleted}`);
          continue;
        }
        
        const msgInfo = lastAssistantMsg.info as AssistantMessage | undefined;
        
        // Clean up the user message
        let cleanUserMessage = userMsg.content;
        const lines = cleanUserMessage.split('\n');
        if (lines.length > 1 && lines[1].includes('Called the')) {
          cleanUserMessage = lines[0];
        }
        cleanUserMessage = cleanUserMessage.replace(/Called the .+ tool.*$/s, '').trim();
        cleanUserMessage = cleanUserMessage.replace(/<file>[\s\S]*?<\/file>/g, '').trim();
        
        // Build conversation history from previous turns
        const conversationHistory = session.messages
          .slice(0, userMsgIndex)
          .map(m => ({
            role: m.role,
            content: m.content.substring(0, 500), // Limit length
            timestamp: m.timestamp
          }));
        
        // Calculate duration
        const userCreated = turnStart;
        const assistantCompleted = turnEnd;
        const actualDuration = assistantCompleted > 0 && userCreated > 0
          ? (assistantCompleted - userCreated) / 1000
          : 0;
        
        const example: DSPyExample = {
          input: {
            task: cleanUserMessage,
            context: session.context || await collectProjectContext(),
            conversationHistory
          },
          actions: turnToolCalls,
          output: {
            response: lastAssistantMsg.content,
            finalMessage: lastAssistantMsg.messageId
          },
          outcome: {
            ...outcome,
            metrics: {
              ...outcome.metrics,
              toolCallCount: turnToolCalls.length
            }
          },
          agent: {
            name: (userMsg.info as UserMessage)?.agent,
            model: `${msgInfo?.providerID}/${msgInfo?.modelID}` || 'unknown',
            temperature: 0.0,
            promptTokens: msgInfo?.tokens?.input || 0,
            completionTokens: msgInfo?.tokens?.output || 0
          },
          metadata: {
            timestamp: lastAssistantMsg.timestamp,
            sessionId: session.sessionId,
            duration: actualDuration,
            messageCount: turnMessages.length
          }
        };
        
        examples.push(example);
        await log(`    ✅ Turn ${i + 1}: Created DSPy example (${turnToolCalls.length} tools, success=${outcome.success})`);
      }
      
      await log(`📊 Created ${examples.length} training example(s) from ${userMessages.length} turn(s)`);
      
      if (examples.length > 0) {
        const dspyFilename = `dspy-${session.sessionId}.json`;
        const dspyFilepath = join(logsDir, dspyFilename);
        
        // Calculate overall session outcome (based on all successful turns)
        const overallSuccess = examples.some(ex => ex.outcome.success);
        const totalToolCalls = examples.reduce((sum, ex) => sum + ex.actions.length, 0);
        
        const dspyContent = JSON.stringify({
          session: session.sessionId,
          generated: new Date().toISOString(),
          totalExamples: examples.length,
          totalTurns: userMessages.length,
          successfulTurns: examples.length,
          overallSuccess,
          totalToolCalls,
          examples,
        }, null, 2);
        
        await writeFile(dspyFilepath, dspyContent, "utf-8");
        await log(`✅ Saved DSPy format: ${examples.length}/${userMessages.length} turns saved`);
      } else {
        await log(`⏭️ No successful turns to save for session ${session.sessionId}`);
      }
    } catch (error) {
      await log(`❌ Error saving DSPy format: ${error}`);
    }
  };
  
  const saveSession = async (session: SessionData) => {
    try {
      const filename = `session-${session.sessionId}.json`;
      const filepath = join(logsDir, filename);
      await writeFile(filepath, JSON.stringify(session, null, 2), "utf-8");
      await log(`✅ Saved session ${session.sessionId} (${session.messages.length} messages, ${session.toolCalls.length} tools)`);
      
      // Also save DSPy format
      await saveDSPyFormat(session);
    } catch (error) {
      await log(`❌ Error saving session: ${error}`);
    }
  };
  
  await log("=== Plugin Initialized (DSPy Enhanced Version) ===");
  console.log("📊 SessionLogger: Initialized (DSPy training data format)");
  
  // Return hooks
  return {
    event: async ({ event }: any) => {
      try {
        const eventType = event.type;
        
        // Handle message.updated events
        if (eventType === "message.updated") {
          const info = event.properties?.info;
          
          if (!info) {
            return;
          }
          
          const sessionId = info.sessionID;
          const messageId = info.id;
          const role = info.role;
          
          if (!sessionId || !messageId || !role) {
            return;
          }
          
          // Initialize session if needed
          if (!sessions.has(sessionId)) {
            const context = await collectProjectContext();
            sessions.set(sessionId, {
              sessionId,
              messages: [],
              toolCalls: [],
              context,
              initialLspDiagnostics: context.lspDiagnostics,
              startTime: Date.now(),
              lastUpdateTime: Date.now(),
            });
            await log(`🆕 New session tracked: ${sessionId}`);
          }
          
          const session = sessions.get(sessionId)!;
          session.lastUpdateTime = Date.now();
          
          // Fetch message content
          try {
            const messageData = await client.session.message({
              path: { id: sessionId, messageID: messageId }
            });
            
            if (messageData.error) {
              await log(`❌ API returned error: ${JSON.stringify(messageData.error)}`);
              return;
            }
            
            if (messageData.data) {
              const textContent = messageData.data.parts
                ?.filter((part: any) => part.type === "text")
                ?.map((part: any) => part.text)
                ?.join("\n") || "";
              
              // Check if message already exists
              const existingIndex = session.messages.findIndex(m => m.messageId === messageId);
              
              if (existingIndex >= 0) {
                session.messages[existingIndex].content = textContent;
                session.messages[existingIndex].info = info;
              } else {
                session.messages.push({
                  messageId,
                  role,
                  timestamp: new Date().toISOString(),
                  content: textContent,
                  info
                });
              }
              
              await log(`✅ Logged ${role} message (${textContent.length} chars)`);
              
              // Auto-save every 5 message updates
              if (!session.updateCount) {
                session.updateCount = 0;
              }
              session.updateCount++;
              if (session.updateCount % 5 === 0) {
                await log(`💾 Auto-saving after ${session.updateCount} updates`);
                await saveSession(session);
              }
            }
          } catch (error) {
            await log(`❌ Error fetching message: ${error}`);
          }
        }
        
        // Save on session.idle
        else if (eventType === "session.idle") {
          const info = event.properties?.info;
          const sessionId = info?.id;
          
          if (sessionId && sessions.has(sessionId)) {
            await log(`💾 Session idle, saving: ${sessionId}`);
            await saveSession(sessions.get(sessionId)!);
          }
        }
        
      } catch (error) {
        await log(`❌ Error in event handler: ${error}`);
      }
    },
    
    // Hook to track tool executions
    "tool.execute.before": async (input, output) => {
      try {
        const { tool, sessionID, callID } = input;
        
        if (!sessions.has(sessionID)) {
          // Session not initialized yet, create it
          const context = await collectProjectContext();
          sessions.set(sessionID, {
            sessionId: sessionID,
            messages: [],
            toolCalls: [],
            context,
            initialLspDiagnostics: context.lspDiagnostics,
            startTime: Date.now(),
            lastUpdateTime: Date.now(),
          });
          await log(`🆕 New session tracked (from tool): ${sessionID}`);
        }
        
        const session = sessions.get(sessionID)!;
        
        // Add tool call tracking with unique callID
        const toolCall = {
          step: session.toolCalls.length + 1,
          tool,
          callID,  // Store unique callID for matching
          args: output.args,
          timestamp: new Date().toISOString()
        };
        session.toolCalls.push(toolCall);
        
        await log(`🔧 Tool call: ${tool} [${callID}] (step ${session.toolCalls.length}) args=${JSON.stringify(output.args).substring(0, 100)}`);
      } catch (error) {
        await log(`❌ Error in tool.execute.before: ${error}`);
      }
    },
    
    // Hook to capture tool results
    "tool.execute.after": async (input, output) => {
      try {
        const { tool, sessionID, callID } = input;
        
        if (!sessions.has(sessionID)) {
          await log(`⚠️ Tool result for unknown session: ${sessionID}`);
          return;
        }
        
        const session = sessions.get(sessionID)!;
        
        // Find the corresponding tool call by callID (unique identifier)
        const toolCall = session.toolCalls.find(tc => tc.callID === callID);
        
        if (toolCall) {
          // Safely extract result text
          let resultText = '';
          if (typeof output.output === 'string') {
            resultText = output.output;
          } else if (output.output && typeof output.output === 'object') {
            resultText = JSON.stringify(output.output);
          }
          
          toolCall.result = resultText;
          toolCall.success = !resultText.toLowerCase().includes('error') && 
                            !resultText.toLowerCase().includes('failed');
          
          await log(`✅ Tool result: ${tool} [${callID}] (success=${toolCall.success})`);
        } else {
          await log(`⚠️ No matching tool call found for callID: ${callID}`);
        }
      } catch (error) {
        await log(`❌ Error in tool.execute.after: ${error}`);
      }
    },
  };
};
