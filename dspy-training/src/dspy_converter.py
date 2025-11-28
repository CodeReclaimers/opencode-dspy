"""
Convert OpenCode session examples to DSPy Example objects.
"""

import dspy
from typing import List, Dict, Any
from pathlib import Path
import json
import logging

from .data_loader import SessionExample

logger = logging.getLogger(__name__)


class DSPyConverter:
    """Converts OpenCode examples to DSPy format"""
    
    def convert_example(self, session_example: SessionExample) -> dspy.Example:
        """Convert a single SessionExample to DSPy Example"""
        
        # Extract the core components DSPy needs
        task = session_example.input.get("task", "")
        context = session_example.input.get("context", {})
        
        # Simplify actions to just tool names and key args
        actions = [
            {
                "tool": action.tool,
                "args": self._simplify_args(action.args),
                "success": action.success
            }
            for action in session_example.actions
        ]
        
        # Create expected output format
        output = {
            "response": session_example.output.get("response", ""),
            "actions": actions,
            "success": session_example.outcome.success
        }
        
        # Create DSPy example with inputs marked
        example = dspy.Example(
            task=task,
            context=context,
            actions=actions,
            expected_response=session_example.output.get("response", ""),
            success=session_example.outcome.success,
            metrics=session_example.outcome.metrics,
        ).with_inputs('task', 'context')
        
        return example
    
    def _simplify_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Simplify tool args to just essential info"""
        # Keep only important args, truncate long strings
        simplified = {}
        for key, value in args.items():
            if isinstance(value, str) and len(value) > 200:
                simplified[key] = value[:197] + "..."
            elif isinstance(value, (dict, list)):
                # Convert complex objects to strings and truncate
                str_val = str(value)
                if len(str_val) > 200:
                    simplified[key] = str_val[:197] + "..."
                else:
                    simplified[key] = value
            else:
                simplified[key] = value
        return simplified
    
    def convert_batch(self, examples: List[SessionExample]) -> List[dspy.Example]:
        """Convert multiple examples"""
        dspy_examples = []
        
        for i, example in enumerate(examples):
            try:
                dspy_ex = self.convert_example(example)
                dspy_examples.append(dspy_ex)
            except Exception as e:
                logger.error(f"Failed to convert example {i}: {e}")
        
        logger.info(f"Converted {len(dspy_examples)} examples to DSPy format")
        return dspy_examples
    
    def save_examples(self, examples: List[dspy.Example], output_path: Path):
        """Save DSPy examples to disk"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        serialized = []
        for ex in examples:
            try:
                serialized.append({
                    "task": ex.task if hasattr(ex, 'task') else "",
                    "context": ex.context if hasattr(ex, 'context') else {},
                    "actions": ex.actions if hasattr(ex, 'actions') else [],
                    "expected_response": ex.expected_response if hasattr(ex, 'expected_response') else "",
                    "success": ex.success if hasattr(ex, 'success') else False,
                    "metrics": ex.metrics if hasattr(ex, 'metrics') else {}
                })
            except Exception as e:
                logger.error(f"Failed to serialize example: {e}")
        
        with open(output_path, 'w') as f:
            json.dump(serialized, f, indent=2)
        
        logger.info(f"Saved {len(examples)} examples to {output_path}")
