"""
OpenCode Exporter - Export optimized prompts for OpenCode consumption.

Supports multiple export formats:
- Agent config (opencode.jsonc snippet)
- Custom instructions (AGENTS.md format)
- Prompt template (full .txt template file)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import dspy
except ImportError:
    dspy = None

logger = logging.getLogger(__name__)


class OpenCodeExporter:
    """Export optimized prompts in OpenCode-compatible formats."""

    def __init__(self, output_dir: str = "./optimized_prompts"):
        """
        Initialize exporter.

        Args:
            output_dir: Directory to save exported prompts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_instruction_prompt(self, module: "dspy.Module") -> str:
        """
        Extract the optimized instruction from a DSPy module.

        Args:
            module: Optimized DSPy module

        Returns:
            Extracted prompt string
        """
        # Debug: Log module structure
        logger.debug(f"Module type: {type(module)}")
        logger.debug(f"Module attributes: {dir(module)}")

        # Try different extraction methods based on module type

        # Method 1: Check all named_predictors (BootstrapFewShot uses this)
        if hasattr(module, 'named_predictors'):
            logger.debug("Module has named_predictors")
            all_demos = []
            for name, predictor in module.named_predictors():
                logger.debug(f"Checking predictor: {name}, type: {type(predictor)}")
                if hasattr(predictor, 'demos') and predictor.demos:
                    logger.info(f"Found {len(predictor.demos)} demonstrations in predictor '{name}'")
                    all_demos.extend(predictor.demos)

            if all_demos:
                return self._format_demos(all_demos)

        # Method 2: BootstrapFewShot stores demos in predictor.demos
        if hasattr(module, 'planner'):
            planner = module.planner
            logger.debug(f"Planner type: {type(planner)}")

            # Check if demos attribute exists (might be empty list)
            if hasattr(planner, 'demos'):
                logger.debug(f"Planner has 'demos' attribute: {type(planner.demos)}, length: {len(planner.demos) if hasattr(planner.demos, '__len__') else 'N/A'}")
                if planner.demos:  # Not empty
                    logger.info(f"Found {len(planner.demos)} demonstrations in planner.demos")
                    return self._format_demos(planner.demos)
                else:
                    logger.debug("Planner.demos exists but is empty")

            # Also check for extended_signature with demos
            if hasattr(planner, 'extended_signature'):
                ext_sig = planner.extended_signature
                if hasattr(ext_sig, 'demos') and ext_sig.demos:
                    logger.info(f"Found {len(ext_sig.demos)} demonstrations in extended signature")
                    return self._format_demos(ext_sig.demos)

        # Method 3: Check module-level demos (some optimizers store here)
        if hasattr(module, 'demos') and module.demos:
            logger.info(f"Found {len(module.demos)} demonstrations at module level")
            return self._format_demos(module.demos)

        # Method 4: ChainOfThought modules might store prompt in signature docstring
        if hasattr(module, 'planner') and hasattr(module.planner, 'signature'):
            sig = module.planner.signature
            if hasattr(sig, '__doc__') and sig.__doc__:
                logger.info("Extracted prompt from signature docstring")
                return sig.__doc__

        # Method 5: Check for instructions in signature
        if hasattr(module, 'planner') and hasattr(module.planner, 'signature'):
            sig = module.planner.signature
            if hasattr(sig, 'instructions') and sig.instructions:
                logger.info("Extracted instructions from signature")
                return sig.instructions

        # Method 6: Serialize the module state as fallback
        logger.warning(
            "Could not find demonstrations or instructions in module. "
            "This may indicate the optimization didn't produce few-shot examples. "
            "Exporting module structure as fallback."
        )
        return self._format_module_structure(module)

    def _format_demos(self, demos: list) -> str:
        """Format few-shot demonstrations as a prompt."""
        parts = ["# Few-Shot Demonstrations\n"]
        parts.append("These examples show how to approach coding tasks effectively.\n")

        for i, demo in enumerate(demos, 1):
            parts.append(f"\n## Example {i}\n")

            # Extract all available fields from the demo
            demo_dict = demo.toDict() if hasattr(demo, 'toDict') else vars(demo)

            for key, value in demo_dict.items():
                # Skip internal fields
                if key.startswith('_'):
                    continue

                # Format field name nicely
                field_name = key.replace('_', ' ').title()
                parts.append(f"**{field_name}:** {value}\n")

        return "\n".join(parts)

    def _format_module_structure(self, module: "dspy.Module") -> str:
        """
        Format module structure in a readable way.

        This is used when we can't extract proper demonstrations.
        """
        parts = ["# Module Configuration\n"]
        parts.append("This optimization did not produce few-shot demonstrations.")
        parts.append("Below is the module structure for reference.\n")

        # Try to extract signature information
        if hasattr(module, 'planner'):
            parts.append("\n## Planner Configuration\n")
            planner = module.planner

            if hasattr(planner, 'signature'):
                sig = planner.signature
                parts.append("### Input Fields:")
                for field_name, field_info in getattr(sig, 'input_fields', {}).items():
                    desc = getattr(field_info, 'desc', 'No description')
                    parts.append(f"- **{field_name}**: {desc}")

                parts.append("\n### Output Fields:")
                for field_name, field_info in getattr(sig, 'output_fields', {}).items():
                    desc = getattr(field_info, 'desc', 'No description')
                    parts.append(f"- **{field_name}**: {desc}")

        parts.append("\n## Usage Note\n")
        parts.append(
            "The optimization completed but did not find demonstrations that improved "
            "performance over the baseline. This can happen when:\n"
            "- The baseline is already performing well\n"
            "- The training set is too small\n"
            "- The metric doesn't capture meaningful improvements\n"
            "\n"
            "Consider:\n"
            "- Running with more training examples\n"
            "- Trying a different optimizer (MIPROv2 or COPRO)\n"
            "- Adjusting the metric weights\n"
            "- Collecting more diverse training data"
        )

        return "\n".join(parts)

    def export_agent_config(
        self,
        optimized_module: "dspy.Module",
        agent_name: str,
        model_name: str,
        baseline_score: float = 0.0,
        optimized_score: float = 0.0
    ) -> Path:
        """
        Export as opencode.jsonc agent configuration snippet.

        This is the primary integration point - users add this to their
        opencode.jsonc to use the optimized prompt.

        Args:
            optimized_module: Optimized DSPy module
            agent_name: Agent name (e.g., "build", "plan")
            model_name: Target model name
            baseline_score: Baseline score before optimization
            optimized_score: Score after optimization

        Returns:
            Path to exported file
        """
        prompt = self.extract_instruction_prompt(optimized_module)

        config = {
            "_comment": f"Optimized {agent_name} agent prompt for {model_name}",
            "_generated": datetime.now().isoformat(),
            "_baseline_score": float(baseline_score),
            "_optimized_score": float(optimized_score),
            "_improvement": float(optimized_score - baseline_score),
            "agent": {
                agent_name: {
                    "prompt": prompt
                }
            }
        }

        # Save as JSONC (JSON with comments)
        output_path = self.output_dir / f"opencode-{agent_name}-{model_name.replace('/', '-')}.jsonc"

        with open(output_path, 'w') as f:
            f.write(f"// Optimized {agent_name} agent prompt\n")
            f.write(f"// Generated: {datetime.now().isoformat()}\n")
            f.write(f"// Target model: {model_name}\n")
            f.write(f"// Baseline score: {baseline_score:.3f}\n")
            f.write(f"// Optimized score: {optimized_score:.3f}\n")
            f.write(f"// Improvement: {optimized_score - baseline_score:+.3f}\n")
            f.write("//\n")
            f.write("// To use: Copy the 'agent' section to your opencode.jsonc\n")
            f.write("\n")
            f.write(json.dumps(config, indent=2))

        logger.info(f"Exported agent config to {output_path}")
        return output_path

    def export_custom_instructions(
        self,
        optimized_module: "dspy.Module",
        filename: str = "OPTIMIZED_AGENT.md"
    ) -> Path:
        """
        Export as AGENTS.md / CLAUDE.md compatible markdown file.

        This appends to the system prompt rather than replacing it.

        Args:
            optimized_module: Optimized DSPy module
            filename: Output filename

        Returns:
            Path to exported file
        """
        prompt = self.extract_instruction_prompt(optimized_module)

        content = f"""# Optimized Agent Instructions

{prompt}

---

*Generated by DSPy optimization on {datetime.now().isoformat()}*

## Usage

Add this to your OpenCode custom instructions by:
1. Copying this file to your project directory
2. Referencing it in opencode.jsonc:
   ```jsonc
   {{
     "instructions": ["{filename}"]
   }}
   ```
"""

        output_path = self.output_dir / filename

        with open(output_path, 'w') as f:
            f.write(content)

        logger.info(f"Exported custom instructions to {output_path}")
        return output_path

    def export_prompt_template(
        self,
        optimized_module: "dspy.Module",
        model_name: str,
        base_template: Optional[str] = None
    ) -> Path:
        """
        Export as a complete prompt template file.

        This can replace model-specific templates like qwen.txt, anthropic.txt, etc.

        Args:
            optimized_module: Optimized DSPy module
            model_name: Model name for filename
            base_template: Optional base template to merge with

        Returns:
            Path to exported file
        """
        prompt = self.extract_instruction_prompt(optimized_module)

        # If we have a base template, merge with it
        if base_template:
            template = base_template + "\n\n" + prompt
        else:
            template = prompt

        output_path = self.output_dir / f"{model_name.replace('/', '-')}-optimized.txt"

        with open(output_path, 'w') as f:
            f.write(template)

        logger.info(f"Exported prompt template to {output_path}")
        return output_path

    def export_all_formats(
        self,
        optimized_module: "dspy.Module",
        agent_name: str,
        model_name: str,
        baseline_score: float = 0.0,
        optimized_score: float = 0.0
    ) -> dict[str, Path]:
        """
        Export in all supported formats.

        Args:
            optimized_module: Optimized DSPy module
            agent_name: Agent name
            model_name: Model name
            baseline_score: Baseline score
            optimized_score: Optimized score

        Returns:
            Dictionary mapping format name to file path
        """
        exports = {}

        exports['agent_config'] = self.export_agent_config(
            optimized_module, agent_name, model_name, baseline_score, optimized_score
        )

        exports['custom_instructions'] = self.export_custom_instructions(
            optimized_module,
            filename=f"OPTIMIZED_{agent_name.upper()}.md"
        )

        exports['prompt_template'] = self.export_prompt_template(
            optimized_module, model_name
        )

        logger.info(f"Exported {len(exports)} formats")
        return exports

    def create_usage_guide(
        self,
        agent_name: str,
        model_name: str,
        export_paths: dict[str, Path]
    ):
        """
        Create a usage guide for the optimized prompts.

        Args:
            agent_name: Agent name
            model_name: Model name
            export_paths: Dictionary of exported file paths
        """
        guide = f"""# Using Optimized {agent_name.title()} Agent for {model_name}

## Quick Start

### Option 1: Agent Configuration (Recommended)

1. Copy the agent configuration:
   ```bash
   cat {export_paths.get('agent_config', 'N/A')}
   ```

2. Add the `agent` section to your `opencode.jsonc`:
   ```jsonc
   {{
     "agent": {{
       "{agent_name}": {{
         "prompt": "..."
       }}
     }}
   }}
   ```

3. Run OpenCode with the optimized agent:
   ```bash
   opencode
   ```

### Option 2: Custom Instructions

1. Copy the instruction file to your project:
   ```bash
   cp {export_paths.get('custom_instructions', 'N/A')} ./
   ```

2. Reference it in `opencode.jsonc`:
   ```jsonc
   {{
     "instructions": ["OPTIMIZED_{agent_name.upper()}.md"]
   }}
   ```

### Option 3: Replace Template

1. Copy the template to OpenCode config:
   ```bash
   cp {export_paths.get('prompt_template', 'N/A')} ~/.config/opencode/prompts/
   ```

2. Configure model to use the template in `opencode.jsonc`:
   ```jsonc
   {{
     "models": {{
       "{model_name}": {{
         "promptTemplate": "{model_name.replace('/', '-')}-optimized.txt"
       }}
     }}
   }}
   ```

## Performance

- **Baseline score**: See exported config file
- **Optimized score**: See exported config file
- **Improvement**: See exported config file

## Troubleshooting

If the optimized prompt doesn't work as expected:

1. Check that the model name matches your configuration
2. Verify the JSON syntax in opencode.jsonc
3. Test with a simple task first
4. Check OpenCode logs for errors

## Re-optimization

To re-optimize with new training data:

```bash
python run_training.py --agent {agent_name} --model {model_name}
```
"""

        guide_path = self.output_dir / f"USAGE_GUIDE_{agent_name}.md"
        with open(guide_path, 'w') as f:
            f.write(guide)

        logger.info(f"Created usage guide at {guide_path}")
        return guide_path
