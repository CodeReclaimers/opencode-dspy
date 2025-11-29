"""
Example Builder - Convert SessionExample objects to DSPy Example format.

This module converts parsed session examples into DSPy-compatible Example objects
suitable for training and evaluation.
"""

import json
import logging
import random
from typing import Optional

try:
    import dspy
except ImportError:
    dspy = None
    logging.warning("DSPy not installed. Install with: pip install dspy-ai")

from .session_parser import SessionExample, ToolAction

logger = logging.getLogger(__name__)


class ExampleBuilder:
    """Build DSPy Example objects from SessionExample data."""

    def __init__(self):
        """Initialize the example builder."""
        if dspy is None:
            raise ImportError("DSPy is required. Install with: pip install dspy-ai")

    def format_context(self, example: SessionExample) -> str:
        """
        Format context information as a string.

        Args:
            example: SessionExample to extract context from

        Returns:
            Formatted context string
        """
        context_parts = []

        # Working directory
        context_parts.append(f"Working Directory: {example.context.working_directory}")

        # File count
        context_parts.append(f"Total Files: {example.context.file_count}")

        # Git status
        if example.context.git_status:
            git = example.context.git_status
            context_parts.append(f"Git Branch: {git.get('branch', 'unknown')}")
            context_parts.append(f"Uncommitted Changes: {git.get('uncommittedChanges', 0)}")

        # LSP diagnostics
        if example.context.lsp_diagnostics:
            errors = example.context.lsp_diagnostics.get('errors', [])
            warnings = example.context.lsp_diagnostics.get('warnings', [])
            context_parts.append(f"LSP Errors: {len(errors)}, Warnings: {len(warnings)}")

        # Relevant files (limited to avoid huge context)
        if example.context.relevant_files:
            num_files = len(example.context.relevant_files)
            context_parts.append(f"Relevant Files ({num_files}):")
            # Show first 20 files
            for file in example.context.relevant_files[:20]:
                context_parts.append(f"  - {file}")
            if num_files > 20:
                context_parts.append(f"  ... and {num_files - 20} more files")

        return "\n".join(context_parts)

    def format_conversation_history(self, example: SessionExample) -> str:
        """
        Format conversation history as a string.

        Args:
            example: SessionExample to extract conversation from

        Returns:
            Formatted conversation string
        """
        if not example.conversation_history:
            return "No prior conversation"

        history_parts = []
        for msg in example.conversation_history:
            history_parts.append(f"[{msg.role}]: {msg.content}")

        return "\n".join(history_parts)

    def extract_tool_sequence(self, example: SessionExample) -> list[str]:
        """
        Extract the sequence of tools used.

        Args:
            example: SessionExample to extract tools from

        Returns:
            List of tool names in order
        """
        return [action.tool for action in example.actions]

    def extract_first_action(self, example: SessionExample) -> Optional[dict]:
        """
        Extract the first tool action as a dict.

        Args:
            example: SessionExample to extract first action from

        Returns:
            First action as dict or None
        """
        if not example.actions:
            return None

        first = example.actions[0]
        return {
            "tool": first.tool,
            "args": first.args
        }

    def format_available_tools(self) -> str:
        """
        Format a description of available tools.

        This is a static list based on OpenCode's tool set.

        Returns:
            Formatted tool list
        """
        tools = [
            "read - Read file contents",
            "write - Write/create a file",
            "edit - Edit existing file with find/replace",
            "bash - Execute bash commands",
            "glob - Find files by pattern",
            "grep - Search file contents",
            "task - Launch sub-agent for complex tasks",
            "todowrite - Manage task list",
            "askuserquestion - Ask user for clarification"
        ]
        return "\n".join(tools)

    def build_dspy_example(
        self,
        session_example: SessionExample,
        include_labels: bool = True
    ) -> dspy.Example:
        """
        Convert a SessionExample to a DSPy Example.

        Args:
            session_example: Parsed session example
            include_labels: Whether to include ground truth labels

        Returns:
            DSPy Example object
        """
        # Build input fields
        example_dict = {
            "task_description": session_example.task,
            "environment_context": self.format_context(session_example),
            "conversation_history": self.format_conversation_history(session_example),
            "available_tools": self.format_available_tools(),
        }

        # Add labels if requested
        if include_labels:
            # Extract expected outputs from the session
            tool_sequence = self.extract_tool_sequence(session_example)
            first_action = self.extract_first_action(session_example)

            example_dict.update({
                "expected_tools": tool_sequence,
                "expected_first_action": first_action,
                "expected_response": session_example.final_response,
                # Include quality metrics for filtering/weighting
                "correctness": session_example.outcome.correctness,
                "efficiency": session_example.outcome.efficiency,
                "minimal_edits": session_example.outcome.minimal_edits,
            })

        # Metadata
        example_dict.update({
            "session_id": session_example.session_id,
            "agent_name": session_example.agent_config.name,
            "model": session_example.agent_config.model,
        })

        # Create DSPy Example
        # Note: DSPy Examples are immutable once created
        return dspy.Example(**example_dict).with_inputs(
            "task_description",
            "environment_context",
            "conversation_history",
            "available_tools"
        )

    def build_batch(
        self,
        session_examples: list[SessionExample],
        include_labels: bool = True
    ) -> list[dspy.Example]:
        """
        Convert multiple SessionExamples to DSPy Examples.

        Args:
            session_examples: List of parsed session examples
            include_labels: Whether to include ground truth labels

        Returns:
            List of DSPy Example objects
        """
        dspy_examples = []

        for session_ex in session_examples:
            try:
                dspy_ex = self.build_dspy_example(session_ex, include_labels=include_labels)
                dspy_examples.append(dspy_ex)
            except Exception as e:
                logger.error(f"Failed to build DSPy example for session {session_ex.session_id}: {e}")
                continue

        logger.info(f"Built {len(dspy_examples)} DSPy examples from {len(session_examples)} sessions")
        return dspy_examples


def split_examples(
    examples: list[dspy.Example],
    train_split: float = 0.7,
    val_split: float = 0.15,
    test_split: float = 0.15,
    random_seed: int = 42,
    stratify_by: Optional[str] = None
) -> tuple[list[dspy.Example], list[dspy.Example], list[dspy.Example]]:
    """
    Split examples into train/val/test sets.

    Args:
        examples: List of DSPy examples
        train_split: Fraction for training (default 0.7)
        val_split: Fraction for validation (default 0.15)
        test_split: Fraction for testing (default 0.15)
        random_seed: Random seed for reproducibility
        stratify_by: Optional field name to stratify by (e.g., "agent_name")

    Returns:
        Tuple of (train, val, test) example lists
    """
    # Validate splits
    total_split = train_split + val_split + test_split
    if abs(total_split - 1.0) > 0.01:
        raise ValueError(f"Splits must sum to 1.0, got {total_split}")

    # Set random seed
    random.seed(random_seed)

    # Stratify if requested
    if stratify_by:
        # Group by stratify field
        groups = {}
        for ex in examples:
            key = getattr(ex, stratify_by, "unknown")
            if key not in groups:
                groups[key] = []
            groups[key].append(ex)

        # Split each group proportionally
        train, val, test = [], [], []
        for group_examples in groups.values():
            shuffled = random.sample(group_examples, len(group_examples))
            n = len(shuffled)
            train_idx = int(n * train_split)
            val_idx = int(n * (train_split + val_split))

            train.extend(shuffled[:train_idx])
            val.extend(shuffled[train_idx:val_idx])
            test.extend(shuffled[val_idx:])

    else:
        # Simple random split
        shuffled = random.sample(examples, len(examples))
        n = len(shuffled)
        train_idx = int(n * train_split)
        val_idx = int(n * (train_split + val_split))

        train = shuffled[:train_idx]
        val = shuffled[train_idx:val_idx]
        test = shuffled[val_idx:]

    logger.info(
        f"Split {len(examples)} examples into "
        f"{len(train)} train, {len(val)} val, {len(test)} test "
        f"(seed={random_seed})"
    )

    return train, val, test


def save_examples(examples: list[dspy.Example], file_path: str):
    """
    Save DSPy examples to a JSON file.

    Args:
        examples: List of DSPy examples
        file_path: Path to save to
    """
    # Convert examples to serializable dicts
    data = []
    for ex in examples:
        # DSPy Examples have a toDict() method
        data.append(ex.toDict() if hasattr(ex, 'toDict') else dict(ex))

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved {len(examples)} examples to {file_path}")


def load_examples(file_path: str) -> list[dspy.Example]:
    """
    Load DSPy examples from a JSON file.

    Args:
        file_path: Path to load from

    Returns:
        List of DSPy examples
    """
    if dspy is None:
        raise ImportError("DSPy is required. Install with: pip install dspy-ai")

    with open(file_path, 'r') as f:
        data = json.load(f)

    examples = [dspy.Example(**ex_dict) for ex_dict in data]
    logger.info(f"Loaded {len(examples)} examples from {file_path}")
    return examples
