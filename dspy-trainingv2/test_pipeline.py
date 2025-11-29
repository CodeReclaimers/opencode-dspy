#!/usr/bin/env python3
"""
Test Pipeline - Validate the DSPy OpenCode optimizer pipeline.

This script tests each component without running expensive optimization.
"""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_data_pipeline():
    """Test session log parsing and DSPy conversion."""
    logger.info("=" * 60)
    logger.info("Testing Data Pipeline")
    logger.info("=" * 60)

    from src.data.session_parser import load_and_parse_sessions
    from src.data.example_builder import ExampleBuilder, split_examples

    # Load sessions
    data_dir = Path("./data")
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return False

    logger.info(f"Loading sessions from {data_dir}")
    try:
        session_examples = load_and_parse_sessions(
            directory=data_dir,
            min_correctness=0.5,  # Lower threshold for testing
            min_efficiency=0.0,
            require_success=True
        )
    except Exception as e:
        logger.error(f"Failed to load sessions: {e}")
        return False

    if not session_examples:
        logger.error("No examples loaded")
        return False

    logger.info(f"✓ Loaded {len(session_examples)} session examples")

    # Print example details
    ex = session_examples[0]
    logger.info(f"\nExample session: {ex.session_id}")
    logger.info(f"  Task: {ex.task[:100]}...")
    logger.info(f"  Agent: {ex.agent_config.name} ({ex.agent_config.model})")
    logger.info(f"  Actions: {len(ex.actions)}")
    logger.info(f"  Correctness: {ex.outcome.correctness:.2f}")
    logger.info(f"  Efficiency: {ex.outcome.efficiency:.2f}")

    # Convert to DSPy format
    logger.info("\nConverting to DSPy format...")
    builder = ExampleBuilder()

    try:
        dspy_examples = builder.build_batch(session_examples, include_labels=True)
    except Exception as e:
        logger.error(f"Failed to convert to DSPy format: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not dspy_examples:
        logger.error("No DSPy examples created")
        return False

    logger.info(f"✓ Converted {len(dspy_examples)} DSPy examples")

    # Print DSPy example details
    dspy_ex = dspy_examples[0]
    logger.info(f"\nDSPy Example:")
    logger.info(f"  Task: {dspy_ex.task_description[:100]}...")
    logger.info(f"  Has environment_context: {bool(dspy_ex.environment_context)}")
    logger.info(f"  Has expected_tools: {hasattr(dspy_ex, 'expected_tools')}")
    if hasattr(dspy_ex, 'expected_tools'):
        logger.info(f"  Expected tools: {dspy_ex.expected_tools[:5]}")

    # Test splitting
    logger.info("\nTesting train/val/test split...")
    try:
        train, val, test = split_examples(dspy_examples, random_seed=42)
        logger.info(f"✓ Split: {len(train)} train, {len(val)} val, {len(test)} test")
    except Exception as e:
        logger.error(f"Failed to split examples: {e}")
        return False

    logger.info("\n✓ Data pipeline test passed!")
    return True


def test_context_builder():
    """Test context building from session examples."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Context Builder")
    logger.info("=" * 60)

    from src.data.session_parser import load_and_parse_sessions
    from src.context.context_builder import ContextBuilder

    # Load one session
    data_dir = Path("./data")
    session_examples = load_and_parse_sessions(
        directory=data_dir,
        min_correctness=0.0,
        require_success=False
    )

    if not session_examples:
        logger.error("No examples to test with")
        return False

    ex = session_examples[0]

    # Build context
    builder = ContextBuilder(opencode_path="/home/alan/opencode")

    try:
        full_prompt = builder.build_prompt_for_example(ex)
        logger.info(f"✓ Built prompt ({len(full_prompt)} chars)")
        logger.info(f"\nPrompt preview (first 500 chars):")
        logger.info(full_prompt[:500])
        logger.info("...")
    except Exception as e:
        logger.error(f"Failed to build context: {e}")
        import traceback
        traceback.print_exc()
        return False

    logger.info("\n✓ Context builder test passed!")
    return True


def test_metrics():
    """Test evaluation metrics."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Metrics")
    logger.info("=" * 60)

    try:
        import dspy
    except ImportError:
        logger.error("DSPy not installed, skipping metric tests")
        return False

    from src.evaluation.metrics import (
        tool_validity_score,
        composite_metric,
        simple_metric
    )

    # Create a mock example and prediction
    example = dspy.Example(
        task_description="Read the file config.py",
        environment_context="Working Directory: /home/user/project",
        available_tools="read, write, edit, bash",
        expected_first_action={"tool": "read", "args": {"filePath": "config.py"}}
    ).with_inputs("task_description", "environment_context", "available_tools")

    # Test with valid prediction
    prediction = dspy.Prediction(
        reasoning="I need to read the config.py file to understand the configuration",
        tool_plan="Use the read tool to examine config.py",
        first_action='{"tool": "read", "args": {"filePath": "config.py"}}'
    )

    logger.info("Testing with valid prediction...")
    tool_score = tool_validity_score(prediction)
    logger.info(f"  Tool validity: {tool_score:.2f}")

    composite_score = composite_metric(example, prediction)
    logger.info(f"  Composite metric: {composite_score:.2f}")

    simple_result = simple_metric(example, prediction)
    logger.info(f"  Simple metric: {simple_result}")

    if tool_score != 1.0:
        logger.error(f"Expected tool validity 1.0, got {tool_score}")
        return False

    # Test with invalid prediction
    bad_prediction = dspy.Prediction(
        reasoning="Let me do something",
        tool_plan="Use invalid tool",
        first_action='{"tool": "invalid_tool", "args": {}}'
    )

    logger.info("\nTesting with invalid prediction...")
    bad_tool_score = tool_validity_score(bad_prediction)
    logger.info(f"  Tool validity: {bad_tool_score:.2f}")

    if bad_tool_score != 0.0:
        logger.error(f"Expected tool validity 0.0, got {bad_tool_score}")
        return False

    logger.info("\n✓ Metrics test passed!")
    return True


def test_agent():
    """Test DSPy agent module."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Agent Module")
    logger.info("=" * 60)

    try:
        import dspy
    except ImportError:
        logger.error("DSPy not installed, skipping agent tests")
        return False

    from src.dspy_modules.code_agent import OpenCodeAgent

    logger.info("Creating OpenCodeAgent...")
    try:
        agent = OpenCodeAgent(use_cot=True)
        logger.info("✓ Agent created successfully")
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return False

    logger.info("\n✓ Agent module test passed!")
    return True


def test_exporter():
    """Test prompt exporter."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Exporter")
    logger.info("=" * 60)

    from src.export.opencode_exporter import OpenCodeExporter

    exporter = OpenCodeExporter(output_dir="./test_outputs")

    logger.info("✓ Exporter created successfully")

    # Note: Can't test export without an actual optimized module
    # That requires running full optimization

    logger.info("\n✓ Exporter test passed!")
    return True


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("DSPy OpenCode Optimizer - Pipeline Test")
    logger.info("=" * 60)

    tests = [
        ("Data Pipeline", test_data_pipeline),
        ("Context Builder", test_context_builder),
        ("Metrics", test_metrics),
        ("Agent Module", test_agent),
        ("Exporter", test_exporter),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"\n{test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    all_passed = all(results.values())

    logger.info("=" * 60)
    if all_passed:
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.error("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
