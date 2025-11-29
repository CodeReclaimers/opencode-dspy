"""
Prompt Templates - Store base prompt templates extracted from OpenCode.

These templates serve as the starting point for DSPy optimization.
They are extracted from the OpenCode source code.
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PromptTemplateLoader:
    """Load prompt templates from OpenCode source."""

    def __init__(self, opencode_path: str = "/home/alan/opencode"):
        """
        Initialize the template loader.

        Args:
            opencode_path: Path to OpenCode source repository
        """
        self.opencode_path = Path(opencode_path)
        self.prompt_dir = self.opencode_path / "packages/opencode/src/session/prompt"
        self._templates = {}

    def load_template(self, template_name: str) -> str:
        """
        Load a prompt template by name.

        Args:
            template_name: Name of the template (without .txt extension)

        Returns:
            Template content as string
        """
        # Check cache first
        if template_name in self._templates:
            return self._templates[template_name]

        # Load from file
        template_file = self.prompt_dir / f"{template_name}.txt"

        if not template_file.exists():
            logger.warning(f"Template file not found: {template_file}")
            return ""

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Cache it
            self._templates[template_name] = content
            logger.debug(f"Loaded template: {template_name}")
            return content

        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            return ""

    def load_all_templates(self) -> dict[str, str]:
        """
        Load all available prompt templates.

        Returns:
            Dictionary mapping template names to content
        """
        if not self.prompt_dir.exists():
            logger.error(f"Prompt directory not found: {self.prompt_dir}")
            return {}

        templates = {}
        for template_file in self.prompt_dir.glob("*.txt"):
            template_name = template_file.stem
            templates[template_name] = self.load_template(template_name)

        logger.info(f"Loaded {len(templates)} prompt templates")
        return templates

    def get_model_prompt(self, model_id: str, provider_id: str = "") -> str:
        """
        Get the appropriate base prompt for a model.

        Args:
            model_id: Model identifier (e.g., "claude-sonnet-4-5", "qwen2.5-coder")
            provider_id: Provider identifier (e.g., "anthropic", "ollama")

        Returns:
            Prompt template content
        """
        # Map models to their default prompts
        # Based on OpenCode's model selection logic

        # Anthropic models
        if "claude" in model_id.lower() or "anthropic" in provider_id.lower():
            return self.load_template("anthropic")

        # Qwen models (common for local/Ollama)
        if "qwen" in model_id.lower():
            return self.load_template("qwen")

        # Gemini models
        if "gemini" in model_id.lower():
            return self.load_template("gemini")

        # OpenAI GPT-4/o series
        if any(x in model_id.lower() for x in ["gpt-4", "gpt-o", "o1", "o3"]):
            return self.load_template("beast")

        # GPT-5/codex
        if "gpt-5" in model_id.lower() or "codex" in model_id.lower():
            return self.load_template("codex")

        # Polaris
        if "polaris" in model_id.lower():
            return self.load_template("polaris")

        # Default to qwen for unknown models (it's a good general-purpose prompt)
        logger.warning(f"Unknown model {model_id}, using qwen template as default")
        return self.load_template("qwen")

    def get_agent_prompt(self, agent_name: str) -> str:
        """
        Get agent-specific prompt override.

        Args:
            agent_name: Name of the agent (e.g., "build", "plan")

        Returns:
            Agent prompt template content
        """
        if agent_name == "plan":
            return self.load_template("plan")
        elif agent_name == "build":
            # Build agent might use build-switch template
            return self.load_template("build-switch")
        else:
            logger.warning(f"Unknown agent {agent_name}")
            return ""

    def get_header_prompt(self, provider_id: str) -> str:
        """
        Get provider-specific header prompt.

        Args:
            provider_id: Provider identifier

        Returns:
            Header prompt content
        """
        if "anthropic" in provider_id.lower():
            return self.load_template("anthropic_spoof")
        return ""


# Default templates extracted from OpenCode (as fallback if source not available)
DEFAULT_TEMPLATES = {
    "qwen": """You are an expert software engineer helping users with coding tasks.

When you use tools:
- Think step-by-step about what information you need
- Use the appropriate tools to gather context before making changes
- Make surgical, focused edits rather than wholesale rewrites
- Verify your changes work before finishing

Key principles:
- Read before you write - always examine existing code first
- Make minimal changes - only modify what's necessary
- Test your changes - verify code works after modifications
- Be precise - use exact file paths and line numbers
""",

    "anthropic": """You are Claude Code, Anthropic's official CLI for Claude.
You are an interactive CLI tool that helps users with software engineering tasks.

Use the instructions below and the tools available to you to assist the user.

# Tone and style
- Your output will be displayed on a command line interface
- Your responses should be short and concise
- You can use Github-flavored markdown for formatting
- Output text to communicate with the user
- Only use tools to complete tasks

# Doing tasks
The user will primarily request you perform software engineering tasks. For these tasks:
- NEVER propose changes to code you haven't read
- Use tools to gather context before making modifications
- Be careful not to introduce security vulnerabilities
- Avoid over-engineering - only make necessary changes
""",

    "plan": """You are in planning mode. Your task is to:

1. Explore the codebase to understand the requirements
2. Design an implementation approach
3. Create a detailed plan of action
4. Present the plan to the user for approval

Do NOT implement the changes yet - focus on planning and design.
""",

    "build-switch": """You are in build mode. Execute the user's request by:

1. Reading necessary files to understand context
2. Making targeted code changes
3. Running tests to verify changes work
4. Committing changes if requested

Focus on implementation, not planning.
"""
}


def get_default_template(template_name: str) -> str:
    """
    Get a default template by name.

    Args:
        template_name: Name of template

    Returns:
        Template content or empty string
    """
    return DEFAULT_TEMPLATES.get(template_name, "")
