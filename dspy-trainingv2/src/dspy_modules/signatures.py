"""
DSPy Signatures - Define task signatures for OpenCode agent optimization.

Signatures define the input/output structure for DSPy modules.
"""

try:
    import dspy
except ImportError:
    dspy = None


if dspy is not None:
    class CodeAgentTask(dspy.Signature):
        """OpenCode agent that performs coding tasks via tool use."""

        # Inputs (these come from session logs)
        task_description: str = dspy.InputField(
            desc="The user's coding request or task to accomplish"
        )
        environment_context: str = dspy.InputField(
            desc="Working directory, file tree, git status, and other environment info"
        )
        conversation_history: str = dspy.InputField(
            desc="Prior messages in the conversation session"
        )
        available_tools: str = dspy.InputField(
            desc="List of tools the agent can use (read, write, edit, bash, etc.)"
        )

        # Outputs we're optimizing for
        reasoning: str = dspy.OutputField(
            desc="Step-by-step reasoning about how to approach the task. Think through what you need to know, what files to examine, and what changes to make."
        )
        tool_plan: str = dspy.OutputField(
            desc="Planned sequence of tool calls to accomplish the task. List the tools you'll use and why."
        )
        first_action: str = dspy.OutputField(
            desc="The first tool call to make, formatted as JSON with 'tool' and 'args' keys"
        )


    class CodeAgentResponse(dspy.Signature):
        """Generate final response after tool execution."""

        task_description: str = dspy.InputField(
            desc="The original user request"
        )
        tool_results: str = dspy.InputField(
            desc="Results from executed tool calls"
        )

        response: str = dspy.OutputField(
            desc="Final response to the user explaining what was done"
        )


    class SimplifiedCodeAgent(dspy.Signature):
        """Simplified signature for faster optimization (single output)."""

        task_description: str = dspy.InputField()
        environment_context: str = dspy.InputField()
        available_tools: str = dspy.InputField()

        # Single combined output
        action_plan: str = dspy.OutputField(
            desc="Reasoning and first tool call. Format: <reasoning>...</reasoning><action>{json}</action>"
        )


    class ToolSelectionTask(dspy.Signature):
        """Focused task: select the right tool for the job."""

        task_description: str = dspy.InputField()
        environment_context: str = dspy.InputField()
        available_tools: str = dspy.InputField()

        selected_tool: str = dspy.OutputField(
            desc="The name of the most appropriate tool to use first"
        )
        reasoning: str = dspy.OutputField(
            desc="Brief explanation of why this tool was selected"
        )

else:
    # Fallback if DSPy not installed
    class CodeAgentTask:
        """Placeholder - DSPy not installed."""
        pass


    class CodeAgentResponse:
        """Placeholder - DSPy not installed."""
        pass


    class SimplifiedCodeAgent:
        """Placeholder - DSPy not installed."""
        pass


    class ToolSelectionTask:
        """Placeholder - DSPy not installed."""
        pass
