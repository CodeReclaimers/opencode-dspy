"""
Session Parser - Parse OpenCode session logs and extract structured training examples.

This module loads JSON session logs from the OpenCode session logger plugin
and converts them into structured SessionExample objects for DSPy training.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextInfo:
    """Context information from the OpenCode session."""
    working_directory: str
    relevant_files: list[str]
    lsp_diagnostics: dict
    git_status: Optional[dict]
    file_count: int


@dataclass
class ToolAction:
    """A single tool call action from the session."""
    step: int
    tool: str
    call_id: str
    args: dict
    timestamp: str
    result: Optional[str] = None
    success: Optional[bool] = None


@dataclass
class Message:
    """A conversation message."""
    role: str
    content: str
    timestamp: str


@dataclass
class Evaluation:
    """Evaluation metrics for the session outcome."""
    correctness: float
    efficiency: float
    minimal_edits: float


@dataclass
class Outcome:
    """Outcome information for the session."""
    success: bool
    task_completed: bool
    correctness: float
    efficiency: float
    minimal_edits: float
    time_to_completion: float
    tool_call_count: int
    lsp_errors_cleared: bool = False
    files_modified: int = 0


@dataclass
class AgentConfig:
    """Agent configuration from the session."""
    name: str
    model: str
    temperature: float
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class SessionExample:
    """A complete training example extracted from a session log."""
    session_id: str
    task: str
    context: ContextInfo
    conversation_history: list[Message]
    actions: list[ToolAction]
    final_response: str
    outcome: Outcome
    agent_config: AgentConfig
    metadata: dict = field(default_factory=dict)


class SessionParser:
    """Parse OpenCode session logs into structured training examples."""

    def __init__(self, min_correctness: float = 0.0, min_efficiency: float = 0.0):
        """
        Initialize the session parser.

        Args:
            min_correctness: Minimum correctness score to include (0-1)
            min_efficiency: Minimum efficiency score to include (0-1)
        """
        self.min_correctness = min_correctness
        self.min_efficiency = min_efficiency

    def load_session_file(self, file_path: Path) -> Optional[dict]:
        """
        Load a single session JSON file.

        Args:
            file_path: Path to the session JSON file

        Returns:
            Parsed session data or None if invalid
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Validate basic structure
            if not isinstance(data, dict):
                logger.warning(f"Invalid session file {file_path}: not a dict")
                return None

            if 'examples' not in data:
                logger.warning(f"Invalid session file {file_path}: missing 'examples' key")
                return None

            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load session file {file_path}: {e}")
            return None

    def load_sessions_from_directory(self, directory: Path) -> list[dict]:
        """
        Load all session JSON files from a directory.

        Args:
            directory: Directory containing session JSON files

        Returns:
            List of parsed session data
        """
        sessions = []
        json_files = list(directory.glob("*.json"))

        logger.info(f"Found {len(json_files)} JSON files in {directory}")

        for file_path in json_files:
            session_data = self.load_session_file(file_path)
            if session_data:
                sessions.append(session_data)

        logger.info(f"Successfully loaded {len(sessions)} session files")
        return sessions

    def parse_context(self, context_data: dict) -> ContextInfo:
        """Parse context information from session data."""
        return ContextInfo(
            working_directory=context_data.get('workingDirectory', ''),
            relevant_files=context_data.get('relevantFiles', []),
            lsp_diagnostics=context_data.get('lspDiagnostics', {}),
            git_status=context_data.get('gitStatus'),
            file_count=context_data.get('fileCount', 0)
        )

    def parse_actions(self, actions_data: list) -> list[ToolAction]:
        """Parse tool actions from session data."""
        actions = []
        for action_data in actions_data:
            action = ToolAction(
                step=action_data.get('step', 0),
                tool=action_data.get('tool', ''),
                call_id=action_data.get('callID', ''),
                args=action_data.get('args', {}),
                timestamp=action_data.get('timestamp', ''),
                result=action_data.get('result'),
                success=action_data.get('success')
            )
            actions.append(action)
        return actions

    def parse_conversation_history(self, history_data: list) -> list[Message]:
        """Parse conversation history from session data."""
        messages = []
        for msg_data in history_data:
            message = Message(
                role=msg_data.get('role', ''),
                content=msg_data.get('content', ''),
                timestamp=msg_data.get('timestamp', '')
            )
            messages.append(message)
        return messages

    def parse_outcome(self, outcome_data: dict) -> Outcome:
        """Parse outcome information from session data."""
        metrics = outcome_data.get('metrics', {})
        evaluation = outcome_data.get('evaluation', {})

        return Outcome(
            success=outcome_data.get('success', False),
            task_completed=outcome_data.get('taskCompleted', False),
            correctness=evaluation.get('correctness', 0.0),
            efficiency=evaluation.get('efficiency', 0.0),
            minimal_edits=evaluation.get('minimalEdits', 0.0),
            time_to_completion=metrics.get('timeToCompletion', 0.0),
            tool_call_count=metrics.get('toolCallCount', 0),
            lsp_errors_cleared=metrics.get('lspErrorsCleared', False),
            files_modified=metrics.get('filesModified', 0)
        )

    def parse_agent_config(self, agent_data: dict) -> AgentConfig:
        """Parse agent configuration from session data."""
        return AgentConfig(
            name=agent_data.get('name', ''),
            model=agent_data.get('model', ''),
            temperature=agent_data.get('temperature', 0.0),
            prompt_tokens=agent_data.get('promptTokens', 0),
            completion_tokens=agent_data.get('completionTokens', 0)
        )

    def parse_example(self, example_data: dict, session_id: str) -> Optional[SessionExample]:
        """
        Parse a single example from session data.

        Args:
            example_data: Example data from session JSON
            session_id: Session ID

        Returns:
            SessionExample or None if parsing fails
        """
        try:
            input_data = example_data.get('input', {})
            output_data = example_data.get('output', {})
            outcome_data = example_data.get('outcome', {})
            agent_data = example_data.get('agent', {})
            metadata = example_data.get('metadata', {})

            # Parse all components
            context = self.parse_context(input_data.get('context', {}))
            actions = self.parse_actions(example_data.get('actions', []))
            conversation_history = self.parse_conversation_history(
                input_data.get('conversationHistory', [])
            )
            outcome = self.parse_outcome(outcome_data)
            agent_config = self.parse_agent_config(agent_data)

            # Create the session example
            example = SessionExample(
                session_id=session_id,
                task=input_data.get('task', ''),
                context=context,
                conversation_history=conversation_history,
                actions=actions,
                final_response=output_data.get('response', ''),
                outcome=outcome,
                agent_config=agent_config,
                metadata=metadata
            )

            return example
        except Exception as e:
            logger.error(f"Failed to parse example from session {session_id}: {e}")
            return None

    def filter_by_quality(self, examples: list[SessionExample]) -> list[SessionExample]:
        """
        Filter examples by quality thresholds.

        Args:
            examples: List of session examples

        Returns:
            Filtered list of examples
        """
        filtered = []
        for example in examples:
            if (example.outcome.correctness >= self.min_correctness and
                example.outcome.efficiency >= self.min_efficiency):
                filtered.append(example)

        logger.info(
            f"Filtered {len(examples)} examples to {len(filtered)} "
            f"(correctness>={self.min_correctness}, efficiency>={self.min_efficiency})"
        )
        return filtered

    def filter_successful(self, examples: list[SessionExample]) -> list[SessionExample]:
        """Filter to only successful examples."""
        successful = [ex for ex in examples if ex.outcome.success]
        logger.info(f"Filtered to {len(successful)}/{len(examples)} successful examples")
        return successful

    def filter_by_agent(self, examples: list[SessionExample], agent_name: str) -> list[SessionExample]:
        """Filter examples by agent name."""
        filtered = [ex for ex in examples if ex.agent_config.name == agent_name]
        logger.info(f"Filtered to {len(filtered)}/{len(examples)} examples from agent '{agent_name}'")
        return filtered

    def parse_sessions(self, session_data_list: list[dict]) -> list[SessionExample]:
        """
        Parse multiple sessions into training examples.

        Args:
            session_data_list: List of session data dicts

        Returns:
            List of SessionExample objects
        """
        all_examples = []

        for session_data in session_data_list:
            session_id = session_data.get('session', 'unknown')
            examples_data = session_data.get('examples', [])

            for example_data in examples_data:
                example = self.parse_example(example_data, session_id)
                if example:
                    all_examples.append(example)

        logger.info(f"Parsed {len(all_examples)} total examples from {len(session_data_list)} sessions")
        return all_examples


def load_and_parse_sessions(
    directory: Path,
    min_correctness: float = 0.8,
    min_efficiency: float = 0.0,
    require_success: bool = True,
    agent_filter: Optional[str] = None
) -> list[SessionExample]:
    """
    Convenience function to load and parse sessions with filtering.

    Args:
        directory: Directory containing session JSON files
        min_correctness: Minimum correctness score (0-1)
        min_efficiency: Minimum efficiency score (0-1)
        require_success: Whether to filter to only successful sessions
        agent_filter: Optional agent name to filter by

    Returns:
        List of filtered SessionExample objects
    """
    parser = SessionParser(min_correctness=min_correctness, min_efficiency=min_efficiency)

    # Load sessions
    session_data = parser.load_sessions_from_directory(directory)

    # Parse examples
    examples = parser.parse_sessions(session_data)

    # Apply filters
    if require_success:
        examples = parser.filter_successful(examples)

    examples = parser.filter_by_quality(examples)

    if agent_filter:
        examples = parser.filter_by_agent(examples, agent_filter)

    return examples
