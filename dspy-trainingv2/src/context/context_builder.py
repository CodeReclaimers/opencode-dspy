"""
Context Builder - Reconstruct OpenCode's layered prompt structure.

This module replicates how OpenCode builds system prompts in layers:
1. Header (provider-specific)
2. Model/Agent prompt (the optimizable layer)
3. Environment (dynamic context)
4. Custom instructions

For DSPy optimization, we want to optimize layer 2 while holding others constant.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ..data.session_parser import ContextInfo
from .prompt_templates import PromptTemplateLoader, get_default_template

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Build OpenCode-compatible system prompts."""

    def __init__(self, opencode_path: Optional[str] = None):
        """
        Initialize the context builder.

        Args:
            opencode_path: Optional path to OpenCode source for loading templates
        """
        if opencode_path:
            self.template_loader = PromptTemplateLoader(opencode_path)
        else:
            self.template_loader = None
            logger.info("No OpenCode path provided, will use default templates")

    def load_template(self, template_name: str) -> str:
        """Load a template, falling back to defaults if needed."""
        if self.template_loader:
            content = self.template_loader.load_template(template_name)
            if content:
                return content

        # Fall back to default
        return get_default_template(template_name)

    def build_environment_block(self, context: ContextInfo) -> str:
        """
        Build the environment section of the prompt.

        Args:
            context: Context information from session

        Returns:
            Formatted environment block
        """
        env_parts = []

        env_parts.append("Here is useful information about the environment you are running in:")
        env_parts.append("<env>")
        env_parts.append(f"Working directory: {context.working_directory}")

        # Git info
        if context.git_status:
            git = context.git_status
            is_git_repo = bool(git.get('branch'))
            env_parts.append(f"Is directory a git repo: {is_git_repo}")
        else:
            env_parts.append("Is directory a git repo: False")

        # Platform (simplified, as we don't track this in session logs)
        env_parts.append("Platform: linux")

        # Date
        env_parts.append(f"Today's date: {date.today().isoformat()}")

        env_parts.append("</env>")

        # File tree section (truncated)
        if context.relevant_files:
            env_parts.append("")
            env_parts.append("Relevant files in the workspace:")
            env_parts.append("<files>")

            # Show up to 50 files
            files_to_show = context.relevant_files[:50]
            for file_path in files_to_show:
                env_parts.append(f"  {file_path}")

            if len(context.relevant_files) > 50:
                remaining = len(context.relevant_files) - 50
                env_parts.append(f"  ... and {remaining} more files")

            env_parts.append("</files>")

        return "\n".join(env_parts)

    def build_git_status_block(self, context: ContextInfo) -> str:
        """
        Build git status information block.

        Args:
            context: Context information from session

        Returns:
            Formatted git status block
        """
        if not context.git_status:
            return ""

        git = context.git_status
        parts = []

        parts.append("gitStatus: This is the git status at the start of the conversation.")
        parts.append(f"Current branch: {git.get('branch', 'unknown')}")
        parts.append("")
        parts.append("Main branch (you will usually use this for PRs): ")
        parts.append("")

        # Include git status output if available
        if git.get('status'):
            parts.append("Status:")
            parts.append(git['status'])

        return "\n".join(parts)

    def build_system_prompt(
        self,
        model_id: str,
        provider_id: str,
        context: ContextInfo,
        agent_name: Optional[str] = None,
        agent_prompt_override: Optional[str] = None,
        custom_instructions: list[str] = None
    ) -> str:
        """
        Reconstruct OpenCode's system prompt structure.

        Args:
            model_id: Model identifier
            provider_id: Provider identifier
            context: Context information from session
            agent_name: Optional agent name (e.g., "build", "plan")
            agent_prompt_override: Optional custom prompt to use (for testing optimized prompts)
            custom_instructions: Optional list of custom instruction strings

        Returns:
            Complete system prompt string
        """
        parts = []

        # Layer 1: Header (provider-specific)
        if "anthropic" in provider_id.lower():
            header = self.load_template("anthropic_spoof")
            if header:
                parts.append(header)

        # Layer 2: Model/Agent prompt (THIS IS WHAT WE OPTIMIZE)
        if agent_prompt_override:
            # Use the provided optimized prompt
            parts.append(agent_prompt_override)
        elif agent_name:
            # Use agent-specific prompt
            if self.template_loader:
                agent_prompt = self.template_loader.get_agent_prompt(agent_name)
            else:
                agent_prompt = get_default_template(agent_name)

            if agent_prompt:
                parts.append(agent_prompt)
            else:
                # Fall back to model default
                if self.template_loader:
                    model_prompt = self.template_loader.get_model_prompt(model_id, provider_id)
                else:
                    model_prompt = get_default_template("qwen")
                parts.append(model_prompt)
        else:
            # Use model default prompt
            if self.template_loader:
                model_prompt = self.template_loader.get_model_prompt(model_id, provider_id)
            else:
                model_prompt = get_default_template("qwen")
            parts.append(model_prompt)

        # Layer 3: Environment (dynamic)
        env_block = self.build_environment_block(context)
        parts.append(env_block)

        # Git status
        git_block = self.build_git_status_block(context)
        if git_block:
            parts.append(git_block)

        # Layer 4: Custom instructions
        if custom_instructions:
            parts.extend(custom_instructions)

        # Join all parts
        return "\n\n".join(parts)

    def build_prompt_for_example(
        self,
        session_example,
        optimized_prompt: Optional[str] = None
    ) -> str:
        """
        Build a complete system prompt for a session example.

        Args:
            session_example: SessionExample object
            optimized_prompt: Optional optimized prompt to test

        Returns:
            Complete system prompt
        """
        return self.build_system_prompt(
            model_id=session_example.agent_config.model,
            provider_id=self._extract_provider(session_example.agent_config.model),
            context=session_example.context,
            agent_name=session_example.agent_config.name,
            agent_prompt_override=optimized_prompt
        )

    def _extract_provider(self, model_id: str) -> str:
        """Extract provider from model ID."""
        if "claude" in model_id.lower():
            return "anthropic"
        elif "gpt" in model_id.lower() or "openai" in model_id.lower():
            return "openai"
        elif "gemini" in model_id.lower():
            return "google"
        elif "ollama" in model_id.lower():
            return "ollama"
        else:
            return "unknown"

    def extract_optimizable_section(self, full_prompt: str) -> str:
        """
        Extract just the optimizable section (Layer 2) from a full prompt.

        This is useful for analyzing what part of the prompt DSPy optimized.

        Args:
            full_prompt: Complete system prompt

        Returns:
            Just the model/agent instruction portion
        """
        # This is a heuristic - look for the section between header and environment
        # In practice, the optimized prompt is what DSPy will modify

        lines = full_prompt.split('\n')

        # Skip header (if present)
        start_idx = 0
        for i, line in enumerate(lines):
            # Skip until we're past any header material
            if "You are" in line or "# " in line:
                start_idx = i
                break

        # Find where environment starts
        end_idx = len(lines)
        for i, line in enumerate(lines[start_idx:], start=start_idx):
            if "<env>" in line or "Here is useful information" in line:
                end_idx = i
                break

        # Extract the middle section
        return '\n'.join(lines[start_idx:end_idx]).strip()
