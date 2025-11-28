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
  const isTaskComplete = (session: SessionData): boolean => {
    const assistantMessages = session.messages.filter(m => m.role === 'assistant');
    if (assistantMessages.length === 0) return false;
    
    const lastMessage = assistantMessages[assistantMessages.length - 1].content;
    
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
      "Ready to use"
    ];
    
    return completionPhrases.some(phrase => 
      lastMessage.toLowerCase().includes(phrase.toLowerCase())
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
  
  // Evaluate session outcome
  const evaluateOutcome = async (session: SessionData): Promise<OutcomeMetrics> => {
    const duration = (session.lastUpdateTime - session.startTime) / 1000;
    const assistantMessages = session.messages.filter(m => m.role === 'assistant');
    const lastAssistantMsg = assistantMessages[assistantMessages.length - 1];
    const msgInfo = lastAssistantMsg?.info as AssistantMessage | undefined;
    
    // Calculate token costs
    const totalInputTokens = session.messages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.input || 0), 0);
    
    const totalOutputTokens = session.messages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.output || 0), 0);
    
    const totalCacheRead = session.messages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.cache?.read || 0), 0);
    
    const totalCacheWrite = session.messages
      .filter(m => m.role === 'assistant' && m.info)
      .reduce((sum, m) => sum + ((m.info as AssistantMessage)?.tokens?.cache?.write || 0), 0);
    
    // Calculate cache hit rate
    const totalTokens = totalInputTokens + totalCacheRead;
    const cacheHitRate = totalTokens > 0 ? totalCacheRead / totalTokens : 0;
    
    // Count files modified from tool calls
    const filesModified = new Set(
      session.toolCalls
        .filter(tc => ['edit', 'write', 'bash'].includes(tc.tool))
        .map(tc => tc.args?.filePath || (tc.tool === 'bash' && tc.args?.command?.includes('rm') ? 'bash-delete' : null))
        .filter(Boolean)
    ).size;
    
    // Check if session had errors
    const hadErrors = session.messages.some(m => 
      m.role === 'assistant' && (m.info as AssistantMessage)?.error
    );
    
    // Check if LSP errors were cleared
    const initialErrors = session.initialLspDiagnostics?.errors?.length || 0;
    const finalErrors = session.context?.lspDiagnostics?.errors?.length || 0;
    const lspErrorsCleared = initialErrors > 0 && finalErrors < initialErrors;
    
    // Get first user message to detect task type
    const firstUserMsg = session.messages.find(m => m.role === 'user');
    const taskType = firstUserMsg ? detectTaskType(firstUserMsg.content) : 'general';
    
    // Check task completion based on type
    const taskComplete = isTaskComplete(session);
    
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
    
    const actualToolCalls = session.toolCalls.length;
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
        toolCallCount: session.toolCalls.length,
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
  
  // Check if session should be saved for training
  const shouldSaveForTraining = (session: SessionData, outcome: OutcomeMetrics): boolean => {
    // Log reasons for not saving
    const reasons = [];
    if (!outcome.success) reasons.push('not successful');
    if (!outcome.taskCompleted) reasons.push('task not completed');
    if (session.toolCalls.length === 0) reasons.push('no tool calls');
    if (session.messages.length < 2) reasons.push('too few messages');
    if (outcome.metrics.timeToCompletion >= 300) reasons.push('took too long');
    
    if (reasons.length > 0) {
      log(`⏭️ Not saving for training: ${reasons.join(', ')}`);
    }
    
    return (
      outcome.success &&                     // Task succeeded
      outcome.taskCompleted &&               // Task was completed (not just started)
      session.toolCalls.length > 0 &&        // Agent took actions
      session.messages.length >= 2 &&        // Has user input and response
      outcome.metrics.timeToCompletion < 300 // Completed in reasonable time (5 min)
    );
  };
  
  // Save session in DSPy format
  const saveDSPyFormat = async (session: SessionData) => {
    try {
      await log(`🔄 Generating DSPy format for session ${session.sessionId}...`);
      
      // Collect final project context
      session.context = await collectProjectContext();
      
      // Evaluate outcome
      const outcome = await evaluateOutcome(session);
      
      // Check if we should save this session
      if (!shouldSaveForTraining(session, outcome)) {
        await log(`⏭️ Skipping session ${session.sessionId} (not successful or incomplete)`);
        await log(`   - success: ${outcome.success}, toolCalls: ${session.toolCalls.length}, messages: ${session.messages.length}`);
        return;
      }
      
      const examples: DSPyExample[] = [];
      
      // Create training examples from user-assistant pairs
      for (let i = 0; i < session.messages.length; i++) {
        const current = session.messages[i];
        
        if (current.role === "user" && current.content) {
          // Find the next assistant message
          let assistantMsg = null;
          let assistantIndex = -1;
          for (let j = i + 1; j < session.messages.length; j++) {
            if (session.messages[j].role === "assistant" && session.messages[j].content) {
              assistantMsg = session.messages[j];
              assistantIndex = j;
              break;
            }
          }
          
          if (assistantMsg && assistantMsg.content) {
            const msgInfo = assistantMsg.info as AssistantMessage | undefined;
            
            // Find tool calls between this user message and assistant response
            const relevantToolCalls = session.toolCalls.filter(tc => {
              const tcTime = new Date(tc.timestamp).getTime();
              const userTime = new Date(current.timestamp).getTime();
              const assistantTime = new Date(assistantMsg!.timestamp).getTime();
              return tcTime >= userTime && tcTime <= assistantTime;
            });
            
            // Get conversation history up to this point
            const conversationHistory = session.messages
              .slice(Math.max(0, i - 6), i)
              .map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp
              }));
            
            const example: DSPyExample = {
              input: {
                task: current.content,
                context: session.context || await collectProjectContext(),
                conversationHistory
              },
              actions: relevantToolCalls,
              output: {
                response: assistantMsg.content,
                finalMessage: assistantMsg.messageId
              },
              outcome: {
                ...outcome,
                metrics: {
                  ...outcome.metrics,
                  toolCallCount: relevantToolCalls.length
                }
              },
              agent: {
                name: (current.info as UserMessage)?.agent,
                model: `${msgInfo?.providerID}/${msgInfo?.modelID}` || 'unknown',
                temperature: 0.0,
                promptTokens: msgInfo?.tokens?.input || 0,
                completionTokens: msgInfo?.tokens?.output || 0
              },
              metadata: {
                timestamp: assistantMsg.timestamp,
                sessionId: session.sessionId,
                duration: (new Date(assistantMsg.timestamp).getTime() - new Date(current.timestamp).getTime()) / 1000,
                messageCount: assistantIndex - i + 1
              }
            };
            
            examples.push(example);
            await log(`    ✅ Created DSPy example from pair ${i}`);
          }
        }
      }
      
      await log(`📊 Created ${examples.length} training examples`);
      
      if (examples.length > 0) {
        const dspyFilename = `dspy-${session.sessionId}.json`;
        const dspyFilepath = join(logsDir, dspyFilename);
        const dspyContent = JSON.stringify({
          session: session.sessionId,
          generated: new Date().toISOString(),
          totalExamples: examples.length,
          outcome,
          examples,
        }, null, 2);
        
        await writeFile(dspyFilepath, dspyContent, "utf-8");
        await log(`✅ Saved DSPy format: ${examples.length} examples (SUCCESS=${outcome.success})`);
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
        session.toolCalls.push({
          step: session.toolCalls.length + 1,
          tool,
          callID,  // Store unique callID for matching
          args: output.args,
          timestamp: new Date().toISOString()
        });
        
        await log(`🔧 Tool call: ${tool} [${callID}] (step ${session.toolCalls.length})`);
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
