"""
Evaluation metrics for DSPy optimization.
"""

import dspy
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class CodingMetric:
    """Metric for evaluating coding agent performance"""
    
    def __init__(self, weights: dict = None):
        self.weights = weights or {
            "success": 0.5,
            "efficiency": 0.3,
            "correctness": 0.2
        }
    
    def __call__(self, example: dspy.Example, prediction: Any, trace: Optional[Any] = None) -> float:
        """
        Evaluate a prediction against ground truth example.
        
        Args:
            example: The ground truth DSPy example
            prediction: The model's prediction
            trace: Optional execution trace from DSPy
            
        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.0
        
        # Success: Did the task complete successfully?
        if hasattr(prediction, 'success') and prediction.success:
            score += self.weights["success"]
        elif hasattr(prediction, 'outcome'):
            if prediction.outcome.get("success", False):
                score += self.weights["success"]
        
        # Efficiency: How many tool calls were needed?
        if hasattr(example, 'actions') and hasattr(prediction, 'actions'):
            expected_tools = len(example.actions)
            actual_tools = len(prediction.actions) if prediction.actions else 0
            
            if expected_tools > 0 and actual_tools > 0:
                # Penalize if using >50% more tools than expected
                efficiency = min(1.0, expected_tools / actual_tools)
                if actual_tools <= expected_tools * 1.5:
                    score += self.weights["efficiency"] * efficiency
        
        # Correctness: Does the response indicate completion?
        if hasattr(prediction, 'response') and hasattr(example, 'expected_response'):
            response_lower = str(prediction.response).lower()
            completion_indicators = ["done", "completed", "successfully", "finished", "added", "fixed"]
            
            if any(indicator in response_lower for indicator in completion_indicators):
                score += self.weights["correctness"]
        
        return score


def simple_success_metric(example: dspy.Example, prediction: Any, trace: Optional[Any] = None) -> float:
    """Simplified metric: just check if task succeeded"""
    if hasattr(prediction, 'success'):
        return 1.0 if prediction.success else 0.0
    if hasattr(prediction, 'outcome'):
        return 1.0 if prediction.outcome.get("success", False) else 0.0
    return 0.0
