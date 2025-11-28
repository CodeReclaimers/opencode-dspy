"""
Export DSPy-optimized prompts to OpenCode format.
"""

from pathlib import Path
import dspy
import logging

logger = logging.getLogger(__name__)


class PromptExporter:
    """Exports optimized DSPy prompts for OpenCode"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(self, optimized_agent: dspy.Module, model_name: str):
        """Export optimized prompts to OpenCode agent format"""
        
        # Extract the optimized prompts from DSPy
        # DSPy stores prompts in the module's predictors
        prompts = self._extract_prompts(optimized_agent)
        
        # Create OpenCode agent markdown file
        agent_content = self._create_agent_markdown(
            model_name=model_name,
            system_prompt=prompts.get("system", ""),
            instructions=prompts.get("instructions", ""),
            examples=prompts.get("examples", [])
        )
        
        # Save to file
        output_file = self.output_dir / f"{model_name.replace('/', '-')}-optimized.md"
        with open(output_file, 'w') as f:
            f.write(agent_content)
        
        logger.info(f"Exported optimized prompt to {output_file}")
        return output_file
    
    def _extract_prompts(self, agent: dspy.Module) -> dict:
        """Extract prompts from optimized DSPy module"""
        prompts = {
            "system": "",
            "instructions": "",
            "examples": []
        }
        
        # Access the ChainOfThought predictor
        if hasattr(agent, 'generate_plan'):
            predictor = agent.generate_plan
            
            # Get the signature (defines input/output)
            if hasattr(predictor, 'extended_signature'):
                sig = predictor.extended_signature
                
                # Extract instructions
                if hasattr(sig, 'instructions') and sig.instructions is not None:
                    prompts["instructions"] = sig.instructions
                
                # Extract few-shot examples
                if hasattr(sig, 'demos') and sig.demos is not None:
                    prompts["examples"] = [
                        {
                            "task": demo.task if hasattr(demo, 'task') and demo.task is not None else "",
                            "response": demo.response if hasattr(demo, 'response') and demo.response is not None else ""
                        }
                        for demo in sig.demos
                    ]
        
        return prompts
    
    def _create_agent_markdown(
        self,
        model_name: str,
        system_prompt: str,
        instructions: str,
        examples: list
    ) -> str:
        """Create OpenCode agent markdown content"""
        
        content = f"""---
description: DSPy-optimized agent for {model_name}
model: {model_name}
temperature: 0.0
---

# DSPy-Optimized Coding Agent

This agent was optimized using DSPy with real OpenCode session data.

## Instructions

{instructions if instructions else "You are a helpful coding assistant that uses tools to complete programming tasks efficiently."}

## Approach

When given a coding task:
1. Analyze the task and available context
2. Plan the minimal set of tool calls needed
3. Execute tools in the correct sequence
4. Verify the outcome matches the requirement

"""
        
        # Add few-shot examples if available
        if examples:
            content += "\n## Examples\n\n"
            for i, example in enumerate(examples, 1):
                content += f"### Example {i}\n\n"
                if example.get("task"):
                    content += f"**Task:** {example['task']}\n\n"
                if example.get("response"):
                    content += f"**Response:** {example['response']}\n\n"
        
        content += """
## Tool Usage Guidelines

- Use the minimum number of tool calls necessary
- Read files before editing them when context is needed
- Verify changes with LSP diagnostics when available
- Indicate completion clearly in your response
"""
        
        return content
