"""
DSPy optimization pipeline.
"""

import dspy
from dspy.teleprompt import MIPROv2, COPRO, BootstrapFewShot
from typing import List, Dict, Any
from pathlib import Path
import logging
import json
import os

logger = logging.getLogger(__name__)


class CodingAgent(dspy.Module):
    """Simple coding agent module for DSPy"""
    
    def __init__(self):
        super().__init__()
        
        # Define the signature: what inputs/outputs the agent handles
        self.generate_plan = dspy.ChainOfThought(
            "task, context -> reasoning, actions, response"
        )
    
    def forward(self, task, context):
        """Process a coding task"""
        result = self.generate_plan(task=task, context=str(context))
        return result


class DSPyOptimizer:
    """Runs DSPy optimization on coding examples"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.setup_models()
    
    def setup_models(self):
        """Configure DSPy with target and teacher models"""
        target_cfg = self.config["models"]["target"]
        teacher_cfg = self.config["models"]["teacher"]
        
        # Target model (the one we're optimizing for)
        if target_cfg["provider"] == "ollama":
            self.target_model = dspy.LM(
                f'ollama_chat/{target_cfg["model"]}',
                api_base='http://localhost:11434',
                temperature=target_cfg.get("temperature", 0.0)
            )
        else:
            self.target_model = dspy.LM(
                f'{target_cfg["provider"]}/{target_cfg["model"]}',
                temperature=target_cfg.get("temperature", 0.0)
            )
        
        # Teacher model (for generating prompts)
        api_key = None
        if "api_key_env" in teacher_cfg:
            api_key = os.getenv(teacher_cfg["api_key_env"])
            if not api_key:
                error_msg = f"API key not found in environment: {teacher_cfg['api_key_env']}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        self.teacher_model = dspy.LM(
            f'{teacher_cfg["provider"]}/{teacher_cfg["model"]}',
            api_key=api_key
        )
        
        # Configure DSPy to use target model
        dspy.configure(lm=self.target_model)
        
        logger.info(f"Target model: {target_cfg['model']}")
        logger.info(f"Teacher model: {teacher_cfg['model']}")
    
    def _validate_optimizer_config(self, opt_cfg: Dict[str, Any], optimizer_name: str):
        """Validate that required config keys exist for the specified optimizer"""
        required_keys = {
            "MIPROv2": ["auto_mode", "num_trials"],
            "COPRO": [],  # depth has a default value
            "BootstrapFewShot": ["max_bootstrapped_demos", "max_labeled_demos"]
        }
        
        if optimizer_name not in required_keys:
            raise ValueError(
                f"Unknown optimizer: {optimizer_name}. "
                f"Supported optimizers: {', '.join(required_keys.keys())}"
            )
        
        missing_keys = [key for key in required_keys[optimizer_name] if key not in opt_cfg]
        
        if missing_keys:
            error_msg = (
                f"Missing required configuration keys for {optimizer_name} optimizer: "
                f"{', '.join(missing_keys)}. Please add them to the optimization section "
                f"in your config file."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def optimize(
        self,
        trainset: List[dspy.Example],
        valset: List[dspy.Example],
        metric: callable
    ) -> dspy.Module:
        """Run DSPy optimization"""
        
        opt_cfg = self.config["optimization"]
        optimizer_name = opt_cfg.get("optimizer")
        
        if not optimizer_name:
            error_msg = "Missing 'optimizer' key in optimization config"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate config has required keys for the selected optimizer
        self._validate_optimizer_config(opt_cfg, optimizer_name)
        
        # Create optimizer based on config
        if optimizer_name == "MIPROv2":
            optimizer = MIPROv2(
                metric=metric,
                auto=opt_cfg["auto_mode"],
                num_trials=opt_cfg["num_trials"],
                prompt_model=self.teacher_model
            )
        elif optimizer_name == "COPRO":
            optimizer = COPRO(
                metric=metric,
                depth=opt_cfg.get("depth", 3)
            )
        elif optimizer_name == "BootstrapFewShot":
            optimizer = BootstrapFewShot(
                metric=metric,
                max_bootstrapped_demos=opt_cfg["max_bootstrapped_demos"],
                max_labeled_demos=opt_cfg["max_labeled_demos"]
            )
        else:
            # This shouldn't happen due to validation, but kept for safety
            raise ValueError(f"Unknown optimizer: {optimizer_name}")
        
        # Create agent and optimize
        logger.info(f"Starting {opt_cfg['optimizer']} optimization...")
        agent = CodingAgent()
        
        optimized_agent = optimizer.compile(
            agent,
            trainset=trainset,
            valset=valset
        )
        
        logger.info("Optimization complete!")
        return optimized_agent
    
    def evaluate(
        self,
        agent: dspy.Module,
        testset: List[dspy.Example],
        metric: callable
    ) -> Dict[str, float]:
        """Evaluate agent on test set"""
        from dspy.evaluate import Evaluate
        
        evaluator = Evaluate(
            devset=testset,
            metric=metric,
            num_threads=1,
            display_progress=True
        )
        
        score = evaluator(agent)
        
        return {
            "score": score,
            "num_examples": len(testset)
        }
