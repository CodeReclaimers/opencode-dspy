"""
Code Agent - DSPy module representing the OpenCode agent.

This module will be optimized by DSPy to improve performance on smaller models.
"""

import json
import logging
from typing import Optional

try:
    import dspy
    from .signatures import CodeAgentTask, CodeAgentResponse, SimplifiedCodeAgent
except ImportError:
    dspy = None
    CodeAgentTask = None
    CodeAgentResponse = None
    SimplifiedCodeAgent = None

logger = logging.getLogger(__name__)


if dspy is not None:
    class OpenCodeAgent(dspy.Module):
        """
        DSPy module representing the OpenCode agent.

        This is what we'll optimize - the module's internal prompts
        will be tuned via DSPy optimizers.
        """

        def __init__(self, use_cot: bool = True):
            """
            Initialize the agent.

            Args:
                use_cot: Whether to use Chain-of-Thought (recommended for optimization)
            """
            super().__init__()

            # Chain-of-thought wrapper adds reasoning scaffolding
            # This is the key module that DSPy will optimize
            if use_cot:
                self.planner = dspy.ChainOfThought(CodeAgentTask)
            else:
                self.planner = dspy.Predict(CodeAgentTask)

            self.responder = dspy.Predict(CodeAgentResponse)

        def forward(
            self,
            task_description: str,
            environment_context: str,
            conversation_history: str = "",
            available_tools: str = "",
            tool_results: Optional[str] = None
        ):
            """
            Forward pass of the agent.

            Args:
                task_description: The user's task
                environment_context: Environment information
                conversation_history: Prior conversation
                available_tools: Available tools
                tool_results: Optional results from tool execution

            Returns:
                dspy.Prediction with reasoning, tool_plan, first_action, and optionally response
            """
            # Planning phase - this is where the magic happens
            plan = self.planner(
                task_description=task_description,
                environment_context=environment_context,
                conversation_history=conversation_history,
                available_tools=available_tools
            )

            if tool_results:
                # Response phase (after tool execution)
                response = self.responder(
                    task_description=task_description,
                    tool_results=tool_results
                )
                return dspy.Prediction(
                    reasoning=plan.reasoning,
                    tool_plan=plan.tool_plan,
                    first_action=plan.first_action,
                    response=response.response
                )

            return plan


    class SimplifiedAgent(dspy.Module):
        """
        Simplified agent for faster optimization.

        Uses a single output instead of multiple fields.
        """

        def __init__(self):
            super().__init__()
            self.agent = dspy.ChainOfThought(SimplifiedCodeAgent)

        def forward(
            self,
            task_description: str,
            environment_context: str,
            available_tools: str
        ):
            """Forward pass."""
            return self.agent(
                task_description=task_description,
                environment_context=environment_context,
                available_tools=available_tools
            )

        def extract_action(self, prediction) -> Optional[dict]:
            """
            Extract the JSON action from the prediction.

            Args:
                prediction: dspy.Prediction

            Returns:
                Parsed action dict or None
            """
            try:
                action_plan = prediction.action_plan

                # Extract JSON from <action>...</action> tags
                if "<action>" in action_plan and "</action>" in action_plan:
                    start = action_plan.find("<action>") + 8
                    end = action_plan.find("</action>")
                    json_str = action_plan[start:end].strip()
                    return json.loads(json_str)

                # Try parsing the whole thing as JSON
                return json.loads(action_plan)

            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.warning(f"Failed to extract action from prediction: {e}")
                return None


    class EvaluableAgent(dspy.Module):
        """
        Agent wrapper that includes evaluation-friendly methods.

        This makes it easier to use the agent in metrics and evaluation.
        """

        def __init__(self, base_agent: Optional[dspy.Module] = None):
            """
            Initialize with an optional base agent.

            Args:
                base_agent: Optional pre-configured agent module
            """
            super().__init__()
            self.agent = base_agent or OpenCodeAgent()

        def forward(
            self,
            task_description: str,
            environment_context: str,
            conversation_history: str = "",
            available_tools: str = ""
        ):
            """Forward pass."""
            return self.agent(
                task_description=task_description,
                environment_context=environment_context,
                conversation_history=conversation_history,
                available_tools=available_tools
            )

        def predict_first_action(
            self,
            task_description: str,
            environment_context: str,
            available_tools: str
        ) -> Optional[dict]:
            """
            Predict the first action as a parsed dict.

            Args:
                task_description: Task description
                environment_context: Environment context
                available_tools: Available tools

            Returns:
                Parsed action dict or None
            """
            prediction = self.forward(
                task_description=task_description,
                environment_context=environment_context,
                available_tools=available_tools
            )

            try:
                return json.loads(prediction.first_action)
            except (json.JSONDecodeError, AttributeError):
                return None

else:
    # Fallback if DSPy not installed
    class OpenCodeAgent:
        """Placeholder - DSPy not installed."""

        def __init__(self, use_cot: bool = True):
            raise ImportError("DSPy is required. Install with: pip install dspy-ai")


    class SimplifiedAgent:
        """Placeholder - DSPy not installed."""

        def __init__(self):
            raise ImportError("DSPy is required. Install with: pip install dspy-ai")


    class EvaluableAgent:
        """Placeholder - DSPy not installed."""

        def __init__(self, base_agent=None):
            raise ImportError("DSPy is required. Install with: pip install dspy-ai")
