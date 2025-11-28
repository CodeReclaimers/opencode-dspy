#!/usr/bin/env python3
"""
Main script to run DSPy training pipeline.
"""

import logging
import yaml
from pathlib import Path
import random
import sys

from src.data_loader import DataLoader
from src.dspy_converter import DSPyConverter
from src.metrics import CodingMetric
from src.optimizer import DSPyOptimizer
from src.prompt_exporter import PromptExporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def partition_data(examples: list, train_split: float, random_seed: int = 42):
    """Partition examples into train and validation sets"""
    # Set random seed for reproducibility
    random.seed(random_seed)
    
    # Shuffle without mutating - random.sample returns a new list
    shuffled = random.sample(examples, len(examples))
    
    # Split
    split_idx = int(len(shuffled) * train_split)
    trainset = shuffled[:split_idx]
    valset = shuffled[split_idx:]
    
    logger.info(f"Data split: {len(trainset)} train, {len(valset)} validation (seed={random_seed})")
    return trainset, valset


def main():
    """Run the complete DSPy training pipeline"""
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()
        
        # Step 1: Load OpenCode session logs
        logger.info("Step 1: Loading session logs...")
        loader = DataLoader(config["data"]["raw_dir"])
        sessions = loader.load_all_sessions()
        
        if not sessions:
            logger.error(f"No session logs found in {config['data']['raw_dir']}")
            logger.error("Please add JSON session logs to the data/raw/ directory")
            sys.exit(1)
        
        if config["data"]["require_success"]:
            sessions = loader.filter_successful(sessions)
            
            if not sessions:
                logger.error("No successful sessions found. Try setting require_success: false in config.yaml")
                sys.exit(1)
        
        examples = loader.extract_examples(sessions)
        
        # Check minimum examples requirement
        min_examples = config["data"]["min_examples"]
        if len(examples) < min_examples:
            logger.error(f"Only {len(examples)} examples found, need at least {min_examples}")
            logger.error("Please collect more training data before running optimization")
            sys.exit(1)
        
        # Step 2: Convert to DSPy format
        logger.info("Step 2: Converting to DSPy format...")
        converter = DSPyConverter()
        dspy_examples = converter.convert_batch(examples)
        
        if not dspy_examples:
            logger.error("Failed to convert any examples to DSPy format")
            sys.exit(1)
        
        # Save processed examples
        processed_dir = Path(config["data"]["processed_dir"])
        processed_dir.mkdir(parents=True, exist_ok=True)
        converter.save_examples(dspy_examples, processed_dir / "examples.json")
        
        # Step 3: Partition data
        logger.info("Step 3: Partitioning data...")
        trainset, valset = partition_data(
            dspy_examples,
            config["data"]["train_split"],
            config["data"].get("random_seed", 42)
        )
        
        if not trainset or not valset:
            logger.error("Failed to create train/validation split")
            sys.exit(1)
        
        # Step 4: Setup metric
        logger.info("Step 4: Setting up evaluation metric...")
        metric = CodingMetric(config["optimization"]["metric_weights"])
        
        # Step 5: Run optimization
        logger.info("Step 5: Running DSPy optimization...")
        optimizer = DSPyOptimizer(config)
        
        optimized_agent = optimizer.optimize(
            trainset=trainset,
            valset=valset,
            metric=metric
        )
        
        # Step 6: Evaluate
        logger.info("Step 6: Evaluating optimized agent...")
        results = optimizer.evaluate(
            agent=optimized_agent,
            testset=valset,
            metric=metric
        )
        
        logger.info(f"Evaluation results: {results}")
        
        # Step 7: Export prompts
        logger.info("Step 7: Exporting optimized prompts...")
        exporter = PromptExporter(config["outputs"]["prompts_dir"])
        
        model_name = config["models"]["target"]["model"]
        prompt_file = exporter.export(optimized_agent, model_name)
        
        logger.info(f"\n{'='*60}")
        logger.info("Training complete!")
        logger.info(f"Optimized prompt saved to: {prompt_file}")
        logger.info(f"Validation score: {results['score']:.2%}")
        logger.info(f"{'='*60}\n")
        
        # Print next steps
        print("\nNext steps:")
        print(f"1. Review the optimized prompt: {prompt_file}")
        print(f"2. Copy it to OpenCode: cp {prompt_file} ~/.config/opencode/agent/")
        print(f"3. Update opencode.json to use the optimized agent")
        print(f"4. Test with: opencode --agent {model_name.replace('/', '-')}-optimized")
        
    except KeyboardInterrupt:
        logger.info("\nTraining interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
