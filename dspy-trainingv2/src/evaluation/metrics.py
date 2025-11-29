"""
Metrics - Evaluation metrics for OpenCode agent optimization.

These metrics align with the session log evaluations and guide DSPy optimization.
"""

import json
import logging
import re
from typing import Optional, Any

try:
    import dspy
except ImportError:
    dspy = None

logger = logging.getLogger(__name__)


# Valid OpenCode tools
VALID_TOOLS = {
    "read", "write", "edit", "bash", "glob", "grep",
    "task", "todowrite", "askuserquestion", "notebookedit",
    "webfetch", "websearch", "bashoutput", "killshell",
    "skill", "slashcommand", "enterplanmode", "exitplanmode"
}


def extract_relevant_terms(environment_context: str) -> list[str]:
    """
    Extract relevant terms from environment context.

    Args:
        environment_context: Environment context string

    Returns:
        List of relevant terms (file names, directories, etc.)
    """
    terms = set()

    # Extract file paths
    for line in environment_context.split('\n'):
        # Look for file paths (containing / or .)
        if '/' in line or '.py' in line or '.js' in line or '.ts' in line:
            # Extract the file name
            parts = line.strip().split()
            for part in parts:
                if '/' in part or '.' in part:
                    terms.add(part.strip('.,;:()[]{}'))

    # Extract words in quotes (likely important entities)
    quoted = re.findall(r'"([^"]+)"', environment_context)
    terms.update(quoted)

    return list(terms)


def extract_tools_from_plan(tool_plan: str) -> list[str]:
    """
    Extract tool names from a tool plan string.

    Args:
        tool_plan: Tool plan string

    Returns:
        List of tool names mentioned
    """
    tools = []
    plan_lower = tool_plan.lower()

    for tool in VALID_TOOLS:
        if tool in plan_lower:
            tools.append(tool)

    return tools


def parse_action_json(action_str: str) -> Optional[dict]:
    """
    Parse an action string as JSON.

    Args:
        action_str: JSON string or formatted action

    Returns:
        Parsed dict or None
    """
    try:
        # Try direct JSON parse
        return json.loads(action_str)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code block
        if "```json" in action_str:
            start = action_str.find("```json") + 7
            end = action_str.find("```", start)
            if end > start:
                try:
                    return json.loads(action_str[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try extracting from <action> tags
        if "<action>" in action_str and "</action>" in action_str:
            start = action_str.find("<action>") + 8
            end = action_str.find("</action>")
            try:
                return json.loads(action_str[start:end].strip())
            except json.JSONDecodeError:
                pass

        return None


def tool_validity_score(prediction: Any) -> float:
    """
    Score: Can we parse the predicted action and is the tool valid?

    Args:
        prediction: dspy.Prediction

    Returns:
        Score from 0.0 to 1.0
    """
    try:
        first_action = getattr(prediction, 'first_action', None)
        if not first_action:
            return 0.0

        action = parse_action_json(first_action)
        if not action:
            return 0.0

        tool = action.get("tool", "").lower()
        return 1.0 if tool in VALID_TOOLS else 0.0

    except Exception as e:
        logger.debug(f"Tool validity check failed: {e}")
        return 0.0


def reasoning_quality_score(example: Any, prediction: Any) -> float:
    """
    Score: Does the reasoning mention relevant files/concepts from context?

    Args:
        example: dspy.Example with environment_context
        prediction: dspy.Prediction with reasoning

    Returns:
        Score from 0.0 to 1.0
    """
    try:
        reasoning = getattr(prediction, 'reasoning', '')
        if not reasoning:
            return 0.0

        environment = getattr(example, 'environment_context', '')
        relevant_terms = extract_relevant_terms(environment)

        if not relevant_terms:
            return 0.5  # Neutral if no terms to check

        # Check how many relevant terms appear in reasoning
        reasoning_lower = reasoning.lower()
        mentions = sum(1 for term in relevant_terms if term.lower() in reasoning_lower)

        # Score based on coverage
        coverage = mentions / len(relevant_terms)
        return min(coverage, 1.0)

    except Exception as e:
        logger.debug(f"Reasoning quality check failed: {e}")
        return 0.0


def plan_coherence_score(example: Any, prediction: Any) -> float:
    """
    Score: Does the plan match expected tool sequence?

    Args:
        example: dspy.Example with expected_tools
        prediction: dspy.Prediction with tool_plan

    Returns:
        Score from 0.0 to 1.0
    """
    try:
        if not hasattr(example, 'expected_tools'):
            return 0.5  # Neutral if no ground truth

        expected_tools = getattr(example, 'expected_tools', [])
        if not expected_tools:
            return 0.5

        tool_plan = getattr(prediction, 'tool_plan', '')
        if not tool_plan:
            return 0.0

        planned_tools = extract_tools_from_plan(tool_plan)

        # Calculate overlap
        expected_set = set(expected_tools[:5])  # First 5 tools
        planned_set = set(planned_tools[:5])

        if not expected_set:
            return 0.5

        overlap = len(expected_set & planned_set)
        return overlap / len(expected_set)

    except Exception as e:
        logger.debug(f"Plan coherence check failed: {e}")
        return 0.0


def first_action_match_score(example: Any, prediction: Any) -> float:
    """
    Score: Does the first action match the ground truth?

    Args:
        example: dspy.Example with expected_first_action
        prediction: dspy.Prediction with first_action

    Returns:
        Score from 0.0 to 1.0
    """
    try:
        if not hasattr(example, 'expected_first_action'):
            return 0.5  # Neutral if no ground truth

        expected = getattr(example, 'expected_first_action')
        if not expected:
            return 0.5

        first_action = getattr(prediction, 'first_action', '')
        predicted = parse_action_json(first_action)

        if not predicted:
            return 0.0

        # Check tool match
        if predicted.get('tool') != expected.get('tool'):
            return 0.0

        # Tool matches - give partial credit
        score = 0.5

        # Check critical args if specified
        critical_args = expected.get('critical_args', [])
        if critical_args:
            args_match = sum(
                1 for arg in critical_args
                if predicted.get('args', {}).get(arg) == expected.get('args', {}).get(arg)
            )
            score += 0.5 * (args_match / len(critical_args))
        else:
            # No critical args specified, full credit for tool match
            score = 1.0

        return score

    except Exception as e:
        logger.debug(f"First action match check failed: {e}")
        return 0.0


def efficiency_score(prediction: Any) -> float:
    """
    Score: Penalize overly verbose reasoning.

    Args:
        prediction: dspy.Prediction

    Returns:
        Score from 0.0 to 1.0
    """
    try:
        reasoning = getattr(prediction, 'reasoning', '')

        # Optimal length: 200-500 characters
        # Too short: < 100 chars (not enough thought)
        # Too long: > 1000 chars (too verbose)

        length = len(reasoning)

        if length < 100:
            return 0.5  # Too short
        elif 200 <= length <= 500:
            return 1.0  # Optimal
        elif length <= 1000:
            return 0.8  # Acceptable
        else:
            # Penalize verbosity
            return max(0.3, 1.0 - (length - 1000) / 2000)

    except Exception as e:
        logger.debug(f"Efficiency check failed: {e}")
        return 0.5


def composite_metric(
    example: Any,
    prediction: Any,
    trace: Optional[Any] = None
) -> float:
    """
    Composite metric combining multiple evaluation criteria.

    This is the primary metric used by DSPy optimizers.

    Args:
        example: dspy.Example
        prediction: dspy.Prediction
        trace: Optional trace (unused)

    Returns:
        Score from 0.0 to 1.0
    """
    # DEBUG: Log prediction details to verify fresh generation
    task = getattr(example, 'task_description', '')[:50] if hasattr(example, 'task_description') else 'unknown'
    first_action = getattr(prediction, 'first_action', '')[:50] if hasattr(prediction, 'first_action') else 'none'
    logger.debug(f"Evaluating: task={task}... action={first_action}...")

    scores = []
    weights = []

    # Tool validity (critical)
    tool_score = tool_validity_score(prediction)
    scores.append(tool_score)
    weights.append(3.0)  # High weight - must be valid

    # Reasoning quality
    reasoning_score = reasoning_quality_score(example, prediction)
    scores.append(reasoning_score)
    weights.append(1.0)

    # Plan coherence
    plan_score = plan_coherence_score(example, prediction)
    scores.append(plan_score)
    weights.append(2.0)  # Important

    # First action match
    action_score = first_action_match_score(example, prediction)
    scores.append(action_score)
    weights.append(2.0)  # Important

    # Efficiency
    eff_score = efficiency_score(prediction)
    scores.append(eff_score)
    weights.append(1.0)

    # Weighted average
    total_weight = sum(weights)
    weighted_sum = sum(s * w for s, w in zip(scores, weights))

    return weighted_sum / total_weight


def correctness_metric(
    example: Any,
    prediction: Any,
    trace: Optional[Any] = None
) -> float:
    """
    Strict correctness: does the first action match ground truth exactly?

    Use this for BootstrapFewShot to select high-quality demonstrations.

    Args:
        example: dspy.Example
        prediction: dspy.Prediction
        trace: Optional trace (unused)

    Returns:
        Score from 0.0 to 1.0
    """
    # Must have valid tool
    if tool_validity_score(prediction) < 1.0:
        return 0.0

    # Must match expected action
    return first_action_match_score(example, prediction)


def simple_metric(
    example: Any,
    prediction: Any,
    trace: Optional[Any] = None
) -> bool:
    """
    Simple binary metric: is the tool valid?

    Good for quick evaluation during development.

    Args:
        example: dspy.Example
        prediction: dspy.Prediction
        trace: Optional trace (unused)

    Returns:
        True if valid, False otherwise
    """
    return tool_validity_score(prediction) >= 1.0
