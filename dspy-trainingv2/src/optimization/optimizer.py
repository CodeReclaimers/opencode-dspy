"""
Optimizer - DSPy optimization pipeline for OpenCode agents.

Supports multiple DSPy optimization strategies:
- BootstrapFewShot: Generate few-shot demonstrations
- MIPROv2: Multi-prompt instruction optimization
- COPRO: Coordinate-ascent prompt optimization
"""

import logging
from typing import Optional, Callable
from pathlib import Path

try:
    import dspy
    from dspy.teleprompt import BootstrapFewShot, COPRO
    # MIPROv2 may not be available in all versions
    try:
        from dspy.teleprompt import MIPROv2
    except ImportError:
        MIPROv2 = None
        logging.warning("MIPROv2 not available in this DSPy version")
except ImportError:
    dspy = None
    BootstrapFewShot = None
    COPRO = None
    MIPROv2 = None

from ..dspy_modules.code_agent import OpenCodeAgent

logger = logging.getLogger(__name__)


def extract_score_value(score_obj) -> float:
    """
    Extract numeric score from DSPy evaluation result.

    DSPy's Evaluate() can return different types depending on version:
    - float/int directly
    - EvaluationResult object with .score attribute
    - Some other numeric type

    Args:
        score_obj: Score object from DSPy evaluation

    Returns:
        Numeric score as float
    """
    # If it's already a number, return it
    if isinstance(score_obj, (int, float)):
        return float(score_obj)

    # If it has a .score attribute (EvaluationResult)
    if hasattr(score_obj, 'score'):
        return float(score_obj.score)

    # If it's a dict with 'score' key
    if isinstance(score_obj, dict) and 'score' in score_obj:
        return extract_score_value(score_obj['score'])

    # Try to convert to float
    try:
        return float(score_obj)
    except (TypeError, ValueError):
        logger.warning(f"Could not extract score from {type(score_obj)}: {score_obj}")
        return 0.0


def configure_dspy_lm(
    model: str,
    provider: str = "openai",
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0
) -> "dspy.LM":
    """
    Configure a DSPy language model with provider-specific settings.

    Args:
        model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-5", "qwen2.5-coder:32b")
        provider: Provider type (openai, anthropic, openai-compatible, ollama)
        api_base: Optional API base URL
        api_key: Optional API key
        temperature: Sampling temperature

    Returns:
        Configured DSPy LM instance
    """
    if dspy is None:
        raise ImportError("DSPy is required. Install with: pip install dspy-ai")

    # Adjust model name based on provider for LiteLLM compatibility
    adjusted_model = model

    # Provider-specific configuration
    if provider == "ollama":
        # Check if using OpenAI-compatible endpoint (/v1)
        if api_base and "/v1" in api_base:
            # Using OpenAI-compatible Ollama endpoint
            # LiteLLM needs openai/ prefix for custom OpenAI-compatible endpoints
            if not model.startswith("openai/"):
                adjusted_model = f"openai/{model}"
                logger.debug(
                    f"Ollama OpenAI-compatible endpoint detected ({api_base}). "
                    f"Using openai/ prefix: {model} -> {adjusted_model}"
                )
        else:
            # Using native Ollama API - need ollama_chat/ prefix
            if not model.startswith("ollama/") and not model.startswith("ollama_chat/"):
                adjusted_model = f"ollama_chat/{model}"
                logger.debug(f"Ollama native API: {model} -> {adjusted_model}")

            if not api_base:
                logger.warning(
                    "Ollama provider with native API requires api_base. "
                    "Using default http://localhost:11434 may not work correctly."
                )

    elif provider == "anthropic":
        # Anthropic models - use default naming
        logger.debug(f"Configuring Anthropic model: {model}")

    elif provider == "openai":
        # OpenAI models or OpenAI-compatible endpoints
        if api_base:
            # Custom OpenAI-compatible endpoint
            # If model name doesn't look like an OpenAI model, add openai/ prefix
            # so LiteLLM uses OpenAI protocol with the custom endpoint
            openai_model_prefixes = ("gpt-", "o1-", "openai/", "text-")
            if not model.startswith(openai_model_prefixes):
                adjusted_model = f"openai/{model}"
                logger.debug(
                    f"Custom OpenAI endpoint with non-OpenAI model detected. "
                    f"Using openai/ prefix: {model} -> {adjusted_model} at {api_base}"
                )
            else:
                logger.debug(f"Configuring OpenAI model: {model} at {api_base}")
        else:
            # Standard OpenAI endpoint
            logger.debug(f"Configuring OpenAI model: {model}")

    elif provider == "openai-compatible":
        # OpenAI-compatible endpoints
        # For most OpenAI-compatible APIs, we use the model name as-is
        # but ensure api_base is set
        if not api_base:
            logger.warning(
                "OpenAI-compatible provider requires api_base. "
                "Using default may not work correctly."
            )
        logger.debug(f"Configuring OpenAI-compatible model: {model} at {api_base}")

    else:
        logger.warning(f"Unknown provider '{provider}', using default DSPy LM initialization")

    # Build kwargs for LM initialization
    lm_kwargs = {
        "model": adjusted_model,
        "temperature": temperature
    }

    # Add API base if specified
    if api_base:
        lm_kwargs["api_base"] = api_base

    # Add API key if specified
    if api_key:
        lm_kwargs["api_key"] = api_key
    elif provider == "ollama" and adjusted_model.startswith("openai/"):
        # CRITICAL: When using Ollama with OpenAI-compatible endpoint (openai/ prefix),
        # LiteLLM requires an api_key parameter even though Ollama doesn't use it.
        # Provide a dummy key to satisfy LiteLLM's requirements.
        lm_kwargs["api_key"] = "ollama-no-key-required"
        logger.debug("Added dummy API key for Ollama OpenAI-compatible endpoint")

    # DEBUG: Log LM kwargs (hide API key for security)
    debug_kwargs = {k: (v[:10] + "..." if k == "api_key" and v else v)
                   for k, v in lm_kwargs.items()}
    logger.debug(f"Creating dspy.LM with kwargs: {debug_kwargs}")

    try:
        lm = dspy.LM(**lm_kwargs)
        logger.info(f"Successfully configured {provider} model: {adjusted_model}")
        return lm
    except Exception as e:
        logger.error(
            f"Failed to configure LM with provider={provider}, "
            f"model={adjusted_model}, api_base={api_base}: {e}"
        )
        logger.error(f"LM kwargs (without api_key): {debug_kwargs}")
        raise


class PromptOptimizer:
    """
    Main optimization orchestrator.

    Supports multiple DSPy optimization strategies with teacher-student setup.
    """

    def __init__(
        self,
        teacher_model: str,
        student_model: str,
        teacher_provider: str = "openai",
        student_provider: str = "ollama",
        teacher_api_base: Optional[str] = None,
        student_api_base: Optional[str] = None,
        teacher_api_key: Optional[str] = None,
        student_api_key: Optional[str] = None,
        teacher_temperature: float = 0.0,
        student_temperature: float = 0.0
    ):
        """
        Initialize the optimizer.

        Args:
            teacher_model: Strong model for generating candidates (e.g., "gpt-4o", "claude-sonnet-4-5")
            student_model: Target model for evaluation (e.g., "qwen2.5-coder:32b")
            teacher_provider: Teacher provider (openai, anthropic, openai-compatible, ollama)
            student_provider: Student provider (openai, anthropic, openai-compatible, ollama)
            teacher_api_base: Optional API base URL for teacher
            student_api_base: Optional API base URL for student
            teacher_api_key: Optional API key for teacher
            student_api_key: Optional API key for student
            teacher_temperature: Temperature for teacher model
            student_temperature: Temperature for student model
        """
        if dspy is None:
            raise ImportError("DSPy is required. Install with: pip install dspy-ai")

        # Initialize language models using the configuration helper
        self.teacher = configure_dspy_lm(
            model=teacher_model,
            provider=teacher_provider,
            api_base=teacher_api_base,
            api_key=teacher_api_key,
            temperature=teacher_temperature
        )

        self.student = configure_dspy_lm(
            model=student_model,
            provider=student_provider,
            api_base=student_api_base,
            api_key=student_api_key,
            temperature=student_temperature
        )

        logger.info(f"Initialized optimizer with teacher={teacher_model} ({teacher_provider}), student={student_model} ({student_provider})")

    def optimize_bootstrap(
        self,
        trainset: list,
        valset: list,
        metric: Callable,
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 4,
        max_rounds: int = 1
    ) -> tuple:
        """
        BootstrapFewShot: Generate demonstrations from teacher, select best ones.

        Good for: Creating few-shot examples that work on smaller models.

        Args:
            trainset: Training examples
            valset: Validation examples
            metric: Evaluation metric function
            max_bootstrapped_demos: Max demonstrations to generate
            max_labeled_demos: Max labeled examples to include
            max_rounds: Max optimization rounds

        Returns:
            Tuple of (optimized_agent, evaluation_results)
        """
        logger.info("Running BootstrapFewShot optimization...")

        # DEBUG: Log which teacher LM is being used
        logger.debug(f"Teacher LM configured: {self.teacher}")

        # NOTE: DSPy caches teacher predictions at temperature=0 for reproducibility and cost savings.
        # This means running the same optimization twice will reuse cached demonstrations.
        # To force fresh predictions, either:
        #   1. Clear the cache: rm -rf ~/.dspy_cache/*
        #   2. Use --no-cache flag (adds small temperature variation)
        #   3. Change the training data or model
        original_teacher_temp = self.teacher.kwargs.get('temperature', 0.0)

        try:
            with dspy.context(lm=self.teacher):
                # DEBUG: Verify context is set to teacher
                logger.debug(f"Current DSPy LM inside optimization context: {dspy.settings.lm}")
                logger.info(f"Optimizing with TEACHER model: {dspy.settings.lm.model if hasattr(dspy.settings.lm, 'model') else 'unknown'}")

                # Track teacher LM calls
                teacher_history_before = len(self.teacher.history)
                logger.debug(f"Teacher LM history before bootstrap: {teacher_history_before}")

                optimizer = BootstrapFewShot(
                    metric=metric,
                    max_bootstrapped_demos=max_bootstrapped_demos,
                    max_labeled_demos=max_labeled_demos,
                    max_rounds=max_rounds
                )

                optimized = optimizer.compile(
                    OpenCodeAgent(),
                    trainset=trainset
                )

                teacher_history_after = len(self.teacher.history)
                teacher_calls_made = teacher_history_after - teacher_history_before
                logger.info(f"Bootstrap complete: teacher made {teacher_calls_made} LLM calls")
        finally:
            # Always restore original temperature
            if original_teacher_temp == 0.0:
                self.teacher.kwargs['temperature'] = original_teacher_temp
                logger.debug(f"Restored teacher temperature to {original_teacher_temp}")

        # Evaluate on student model
        logger.info("Evaluating optimized agent on student model...")
        eval_results = self._evaluate_on_student(optimized, valset, metric)

        return optimized, eval_results

    def optimize_mipro(
        self,
        trainset: list,
        valset: list,
        metric: Callable,
        num_candidates: int = 10,
        init_temperature: float = 1.0,
        minibatch_size: int = None
    ) -> tuple:
        """
        MIPROv2: Multi-prompt instruction optimization.

        Good for: Finding optimal instruction phrasing for the agent prompt.
        This is likely the best approach for smaller model optimization.

        Args:
            trainset: Training examples
            valset: Validation examples
            metric: Evaluation metric function
            num_candidates: Number of prompt candidates to generate
            init_temperature: Initial temperature for generation
            minibatch_size: Size of minibatches for evaluation (defaults to min(25, len(valset)))

        Returns:
            Tuple of (optimized_agent, evaluation_results)
        """
        if MIPROv2 is None:
            raise ImportError("MIPROv2 not available in this DSPy version")

        logger.info("Running MIPROv2 optimization...")

        # Auto-adjust minibatch_size to fit dataset
        if minibatch_size is None:
            # Default to smaller of 25 or validation set size
            minibatch_size = min(25, len(valset))
            logger.info(f"Auto-set minibatch_size to {minibatch_size} (valset size: {len(valset)})")
        elif minibatch_size > len(valset):
            logger.warning(
                f"minibatch_size ({minibatch_size}) exceeds valset size ({len(valset)}). "
                f"Reducing to {len(valset)}"
            )
            minibatch_size = len(valset)

        # CRITICAL: Bypass DSPy cache for teacher model
        original_teacher_temp = self.teacher.kwargs.get('temperature', 0.0)
        if original_teacher_temp == 0.0:
            logger.info("Temporarily setting teacher temperature=0.001 to bypass DSPy cache...")
            self.teacher.kwargs['temperature'] = 0.001
        else:
            logger.debug(f"Teacher already has non-zero temperature ({original_teacher_temp}), cache bypassed")

        try:
            with dspy.context(lm=self.teacher):
                # Note: Setting auto=None to allow manual control of num_candidates and num_trials
                # Alternative: Remove num_candidates/num_trials and let auto='light'/'medium'/'heavy'
                optimizer = MIPROv2(
                    metric=metric,
                    auto=None,  # Disable auto mode to use manual parameters
                    num_candidates=num_candidates,
                    init_temperature=init_temperature
                )

                optimized = optimizer.compile(
                    OpenCodeAgent(),
                    trainset=trainset,
                    num_trials=len(trainset),
                    minibatch_size=minibatch_size,
                    valset=valset
                )
        finally:
            # Always restore original temperature
            if original_teacher_temp == 0.0:
                self.teacher.kwargs['temperature'] = original_teacher_temp
                logger.debug(f"Restored teacher temperature to {original_teacher_temp}")

        # Evaluate on student model
        logger.info("Evaluating optimized agent on student model...")
        eval_results = self._evaluate_on_student(optimized, valset, metric)

        return optimized, eval_results

    def optimize_copro(
        self,
        trainset: list,
        valset: list,
        metric: Callable,
        depth: int = 3,
        breadth: int = 10
    ) -> tuple:
        """
        COPRO: Coordinate-ascent prompt optimization.

        Good for: Iteratively refining prompt components.

        Args:
            trainset: Training examples
            valset: Validation examples (used for final evaluation only)
            metric: Evaluation metric function
            depth: Optimization depth (iterations)
            breadth: Breadth (candidates per iteration)

        Returns:
            Tuple of (optimized_agent, evaluation_results)
        """
        logger.info("Running COPRO optimization...")

        # CRITICAL: Bypass DSPy cache for teacher model
        original_teacher_temp = self.teacher.kwargs.get('temperature', 0.0)
        if original_teacher_temp == 0.0:
            logger.info("Temporarily setting teacher temperature=0.001 to bypass DSPy cache...")
            self.teacher.kwargs['temperature'] = 0.001
        else:
            logger.debug(f"Teacher already has non-zero temperature ({original_teacher_temp}), cache bypassed")

        try:
            with dspy.context(lm=self.teacher):
                optimizer = COPRO(
                    metric=metric,
                    depth=depth,
                    breadth=breadth,
                    verbose=True
                )

                # Note: COPRO requires eval_kwargs but sets devset=trainset internally
                # So we pass eval_kwargs but don't include 'devset' to avoid conflict
                optimized = optimizer.compile(
                    OpenCodeAgent(),
                    trainset=trainset,
                    eval_kwargs={}  # Empty dict - COPRO sets devset and metric internally
                )
        finally:
            # Always restore original temperature
            if original_teacher_temp == 0.0:
                self.teacher.kwargs['temperature'] = original_teacher_temp
                logger.debug(f"Restored teacher temperature to {original_teacher_temp}")

        # Evaluate on student model
        logger.info("Evaluating optimized agent on student model...")
        eval_results = self._evaluate_on_student(optimized, valset, metric)

        return optimized, eval_results

    def _evaluate_on_student(
        self,
        module: "dspy.Module",
        examples: list,
        metric: Callable,
        num_threads: int = 1,
        display_progress: bool = True
    ) -> dict:
        """
        Evaluate optimized module on student (target) model.

        Args:
            module: Optimized DSPy module
            examples: Examples to evaluate on
            metric: Evaluation metric
            num_threads: Number of parallel threads
            display_progress: Whether to show progress

        Returns:
            Dictionary with evaluation results
        """
        # DEBUG: Log which LM is configured before context
        logger.debug(f"Student LM configured: {self.student}")
        logger.debug(f"Current DSPy LM before context: {dspy.settings.lm if hasattr(dspy.settings, 'lm') else 'None'}")

        # CRITICAL: DSPy caches LM calls at temperature=0 to avoid redundant API requests.
        # This causes student evaluation to return cached predictions from previous models!
        #
        # SOLUTION: Temporarily use temperature > 0 to bypass caching.
        # A tiny temperature (0.001) has minimal impact on output while ensuring fresh predictions.
        # This avoids breaking DSPy's cache database structure (which clearing the cache does).

        original_student_temp = self.student.kwargs.get('temperature', 0.0)
        if original_student_temp == 0.0:
            logger.info("Temporarily setting student temperature=0.001 to bypass DSPy cache and force fresh predictions...")
            self.student.kwargs['temperature'] = 0.001
        else:
            logger.debug(f"Student already has non-zero temperature ({original_student_temp}), cache bypassed")

        from copy import deepcopy

        with dspy.context(lm=self.student):
            # CRITICAL: Create module INSIDE the context so it uses the student LM
            fresh_module = OpenCodeAgent()
            logger.debug("Created fresh module inside student context")

            # Copy demos from optimized module (if any)
            if hasattr(module, 'named_predictors') and hasattr(fresh_module, 'named_predictors'):
                for (opt_name, opt_pred), (fresh_name, fresh_pred) in zip(
                    module.named_predictors(),
                    fresh_module.named_predictors()
                ):
                    if hasattr(opt_pred, 'demos') and opt_pred.demos:
                        fresh_pred.demos = deepcopy(opt_pred.demos)
                        logger.debug(f"Copied {len(fresh_pred.demos)} demos to fresh predictor '{fresh_name}'")
            # DEBUG: Verify context is set to student
            logger.debug(f"Current DSPy LM inside context: {dspy.settings.lm}")
            logger.info(f"Evaluating on STUDENT model: {dspy.settings.lm.model if hasattr(dspy.settings.lm, 'model') else 'unknown'}")

            # Create evaluator
            from dspy.evaluate import Evaluate

            # DEBUG: Verify examples are not empty
            logger.debug(f"Examples to evaluate: {len(examples)}")
            if examples:
                ex = examples[0]
                logger.debug(f"  First example task: {getattr(ex, 'task_description', 'N/A')[:80]}")
                logger.debug(f"  First example has answer: {hasattr(ex, 'first_action')}")

                # CRITICAL: Check if examples have input_keys set!
                logger.debug(f"  First example _input_keys: {getattr(ex, '_input_keys', 'MISSING!')}")
                logger.debug(f"  First example keys: {ex.keys() if hasattr(ex, 'keys') else 'N/A'}")

                # Try calling inputs() to see if it raises an error
                try:
                    inputs = ex.inputs()
                    logger.debug(f"  First example inputs() succeeded: {list(inputs.keys())}")
                except Exception as e:
                    logger.error(f"  First example inputs() FAILED: {e}")
                    logger.error(f"  THIS IS THE ROOT CAUSE! Examples need .with_inputs(...)")

            # DEBUG: Wrap metric to trace calls
            call_count = {'count': 0}
            original_metric = metric

            def traced_metric(example, prediction, trace=None):
                call_count['count'] += 1
                logger.debug(f"Metric called #{call_count['count']}")
                logger.debug(f"  Prediction type: {type(prediction)}")
                logger.debug(f"  Has first_action: {hasattr(prediction, 'first_action')}")
                result = original_metric(example, prediction, trace)
                logger.debug(f"  Metric result: {result}")
                return result

            evaluator = Evaluate(
                devset=examples,
                metric=traced_metric,
                num_threads=num_threads,
                display_progress=display_progress,
                display_table=False,
                provide_traceback=True  # ✅ Show actual errors instead of silent failure!
            )

            # Run evaluation - cache has been cleared, so will make fresh LLM calls
            logger.info(f"Starting evaluation of {len(examples)} examples with student model...")

            # Track calls using DSPy's LM history (LiteLLM callbacks don't work with DSPy)
            # IMPORTANT: Use self.student.history, not dspy.settings.lm.history
            # because dspy.settings.lm might be None before the context manager
            history_before = len(self.student.history) if hasattr(self.student, 'history') else 0
            logger.debug(f"Student LM history before evaluation: {history_before}")

            # Run evaluation
            try:
                logger.debug(f"About to call evaluator on fresh_module...")
                logger.debug(f"  Module type: {type(fresh_module)}")
                logger.debug(f"  Module has forward: {hasattr(fresh_module, 'forward')}")

                # Check module predictor states
                if hasattr(fresh_module, 'named_predictors'):
                    for name, pred in fresh_module.named_predictors():
                        logger.debug(f"  Predictor '{name}': type={type(pred)}, has demos={hasattr(pred, 'demos')}")
                        if hasattr(pred, 'demos') and pred.demos:
                            logger.debug(f"    -> {len(pred.demos)} demos")
                        if hasattr(pred, '_compiled'):
                            logger.debug(f"    -> _compiled={pred._compiled}")

                logger.debug(f"  Evaluator type: {type(evaluator)}")
                logger.debug(f"  Evaluator devset size: {len(evaluator.devset)}")
                score = evaluator(fresh_module)
                logger.debug(f"Evaluator returned: {score}")
                logger.debug(f"  Score type: {type(score)}")
                logger.debug(f"  Score value: {score}")
                if hasattr(score, 'results') and score.results:
                    logger.debug(f"  First result: {score.results[0]}")
                    first_result = score.results[0]
                    if hasattr(first_result, '__dict__'):
                        logger.debug(f"  First result attributes: {first_result.__dict__}")
                    else:
                        logger.debug(f"  First result (tuple/list): {first_result}")
            except Exception as e:
                logger.error(f"Exception during evaluation: {e}", exc_info=True)
                raise

            # Count actual LLM calls made
            history_after = len(self.student.history) if hasattr(self.student, 'history') else 0
            num_calls = history_after - history_before
            logger.debug(f"Student LM history after evaluation: {history_after}")

            # Extract numeric score
            numeric_score = extract_score_value(score)

            # DEBUG: Report metric calls
            logger.info(f"Evaluation complete: score={numeric_score:.3f}, metric called {call_count['count']} times, made {num_calls} LLM calls")

        # Restore original temperature
        if original_student_temp == 0.0:
            self.student.kwargs['temperature'] = original_student_temp
            logger.debug(f"Restored student temperature to {original_student_temp}")

        return {
            "score": numeric_score,
            "num_examples": len(examples)
        }

    def evaluate_baseline(
        self,
        examples: list,
        metric: Callable
    ) -> dict:
        """
        Evaluate baseline (unoptimized) agent.

        Args:
            examples: Examples to evaluate
            metric: Evaluation metric

        Returns:
            Dictionary with baseline results
        """
        logger.info("Evaluating baseline agent (should use STUDENT model)...")

        baseline = OpenCodeAgent()
        return self._evaluate_on_student(baseline, examples, metric)


class ExperimentTracker:
    """Track optimization experiments and results."""

    def __init__(self, output_dir: str):
        """
        Initialize tracker.

        Args:
            output_dir: Directory to save experiment results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []

    def log_experiment(
        self,
        name: str,
        optimizer_type: str,
        baseline_score: float,
        optimized_score: float,
        config: dict,
        model: str
    ):
        """
        Log an experiment result.

        Args:
            name: Experiment name
            optimizer_type: Type of optimizer used
            baseline_score: Baseline score
            optimized_score: Optimized score
            config: Optimizer configuration
            model: Target model
        """
        result = {
            "name": name,
            "optimizer": optimizer_type,
            "model": model,
            "baseline_score": float(baseline_score),
            "optimized_score": float(optimized_score),
            "improvement": float(optimized_score - baseline_score),
            "config": config
        }

        self.results.append(result)
        logger.info(
            f"Experiment '{name}': baseline={baseline_score:.3f}, "
            f"optimized={optimized_score:.3f}, improvement={result['improvement']:.3f}"
        )

    def save_results(self, filename: str = "experiment_results.json"):
        """
        Save results to JSON file.

        Args:
            filename: Output filename
        """
        import json

        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Saved experiment results to {output_path}")

    def get_best_experiment(self) -> Optional[dict]:
        """
        Get the best experiment by improvement.

        Returns:
            Best experiment dict or None
        """
        if not self.results:
            return None

        return max(self.results, key=lambda x: x['improvement'])
