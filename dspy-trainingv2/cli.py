#!/usr/bin/env python3
"""
DSPy Prompt Optimizer for OpenCode - CLI Interface

This script provides a command-line interface for optimizing OpenCode agent prompts
using DSPy and session logs.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import yaml

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    print("Error: Required packages not installed.")
    print("Install with: pip install typer rich")
    sys.exit(1)

try:
    import dspy
except ImportError:
    print("Error: DSPy not installed.")
    print("Install with: pip install dspy-ai")
    sys.exit(1)

logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load from .env in current directory
    load_dotenv(Path(__file__).parent.parent / ".env")  # Also try parent directory
    logger.debug("Loaded environment variables from .env file(s)")
except ImportError:
    logger.debug("python-dotenv not installed, skipping .env file loading")
except Exception as e:
    logger.debug(f"Error loading .env file: {e}")

from src.data.session_parser import load_and_parse_sessions
from src.data.example_builder import ExampleBuilder, split_examples
from src.evaluation.metrics import composite_metric, correctness_metric, simple_metric
from src.optimization.optimizer import PromptOptimizer, ExperimentTracker
from src.export.opencode_exporter import OpenCodeExporter

app = typer.Typer(help="DSPy Prompt Optimizer for OpenCode")
console = Console()


def setup_logging(config: dict):
    """Setup logging based on config."""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Configure root logger
    logging.basicConfig(level=level, format=format_str)

    # File handler if specified
    log_file = log_config.get('file')
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(format_str))
        logging.getLogger().addHandler(file_handler)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_metric(metric_name: str):
    """Get metric function by name."""
    metrics = {
        'composite': composite_metric,
        'correctness': correctness_metric,
        'simple': simple_metric
    }
    return metrics.get(metric_name, composite_metric)


def get_api_key(env_var: Optional[str]) -> Optional[str]:
    """Get API key from environment variable."""
    if not env_var:
        return None
    return os.getenv(env_var)


@app.command()
def train(
    config: Path = typer.Option("config/default.yaml", help="Configuration file path"),
    experiment_name: str = typer.Option(None, help="Name for this experiment"),
    optimizer: str = typer.Option(None, help="Optimizer: bootstrap, mipro, copro"),
    output_dir: str = typer.Option(None, help="Override output directory"),
):
    """Run prompt optimization training."""

    # Load config
    cfg = load_config(str(config))
    setup_logging(cfg)

    console.print("[bold blue]DSPy OpenCode Prompt Optimizer[/bold blue]")
    console.print()

    # Set defaults from config
    if not experiment_name:
        from datetime import datetime
        experiment_name = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if not optimizer:
        optimizer = cfg['optimization']['default_optimizer']

    if not output_dir:
        output_dir = cfg['output']['base_dir']

    console.print(f"[yellow]Experiment:[/yellow] {experiment_name}")
    console.print(f"[yellow]Optimizer:[/yellow] {optimizer}")
    console.print()

    # Step 1: Load and parse session logs
    console.print("[bold]Step 1: Loading session logs...[/bold]")

    session_logs_dir = Path(cfg['data']['session_logs_dir'])
    if not session_logs_dir.exists():
        console.print(f"[red]Error: Session logs directory not found: {session_logs_dir}[/red]")
        raise typer.Exit(1)

    try:
        session_examples = load_and_parse_sessions(
            directory=session_logs_dir,
            min_correctness=cfg['data']['min_correctness'],
            min_efficiency=cfg['data']['min_efficiency'],
            require_success=cfg['data']['require_success'],
            agent_filter=cfg['data']['agent_filter']
        )
    except Exception as e:
        console.print(f"[red]Error loading sessions: {e}[/red]")
        raise typer.Exit(1)

    if not session_examples:
        console.print("[red]No training examples found![/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Loaded {len(session_examples)} examples[/green]")

    # Check minimum examples
    if len(session_examples) < cfg['data']['min_examples']:
        console.print(f"[red]Error: Only {len(session_examples)} examples found, need at least {cfg['data']['min_examples']}[/red]")
        raise typer.Exit(1)

    # Step 2: Convert to DSPy format
    console.print("\n[bold]Step 2: Converting to DSPy format...[/bold]")

    builder = ExampleBuilder()
    dspy_examples = builder.build_batch(session_examples, include_labels=True)

    console.print(f"[green]✓ Converted {len(dspy_examples)} examples to DSPy format[/green]")

    # Step 3: Split into train/val/test
    console.print("\n[bold]Step 3: Splitting data...[/bold]")

    train, val, test = split_examples(
        dspy_examples,
        train_split=cfg['data']['train_split'],
        val_split=cfg['data']['val_split'],
        test_split=cfg['data']['test_split'],
        random_seed=cfg['data']['random_seed']
    )

    console.print(f"[green]✓ Train: {len(train)}, Val: {len(val)}, Test: {len(test)}[/green]")

    # Step 4: Setup models
    console.print("\n[bold]Step 4: Setting up models...[/bold]")

    teacher_cfg = cfg['models']['teacher']
    student_cfg = cfg['models']['student']

    teacher_key = get_api_key(teacher_cfg.get('api_key_env'))
    student_key = get_api_key(student_cfg.get('api_key_env'))

    # DEBUG: Log API key status (hide actual keys)
    logger.debug(f"Teacher api_key_env: {teacher_cfg.get('api_key_env')}")
    logger.debug(f"Teacher API key loaded: {bool(teacher_key)} (length: {len(teacher_key) if teacher_key else 0})")
    logger.debug(f"Student api_key_env: {student_cfg.get('api_key_env')}")
    logger.debug(f"Student API key loaded: {bool(student_key)} (length: {len(student_key) if student_key else 0})")

    try:
        opt = PromptOptimizer(
            teacher_model=teacher_cfg['model'],
            student_model=student_cfg['model'],
            teacher_provider=teacher_cfg.get('provider', 'openai'),
            student_provider=student_cfg.get('provider', 'ollama'),
            teacher_api_base=teacher_cfg.get('api_base'),
            student_api_base=student_cfg.get('api_base'),
            teacher_api_key=teacher_key,
            student_api_key=student_key,
            teacher_temperature=teacher_cfg.get('temperature', 0.0),
            student_temperature=student_cfg.get('temperature', 0.0)
        )
    except Exception as e:
        console.print(f"[red]Error setting up optimizer: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

    console.print(f"[green]✓ Teacher: {teacher_cfg['model']} ({teacher_cfg.get('provider', 'openai')})[/green]")
    console.print(f"[green]✓ Student: {student_cfg['model']} ({student_cfg.get('provider', 'ollama')})[/green]")

    # Step 5: Evaluate baseline
    console.print("\n[bold]Step 5: Evaluating baseline...[/bold]")

    metric = get_metric(cfg['evaluation']['primary_metric'])

    try:
        baseline_results = opt.evaluate_baseline(val, metric)
        baseline_score = baseline_results['score']
        console.print(f"[green]✓ Baseline score: {baseline_score:.3f}[/green]")
    except Exception as e:
        console.print(f"[red]Error evaluating baseline: {e}[/red]")
        raise typer.Exit(1)

    # Step 6: Run optimization
    console.print(f"\n[bold]Step 6: Running {optimizer} optimization...[/bold]")
    console.print("[yellow]This may take a while...[/yellow]")

    try:
        if optimizer == "bootstrap":
            opt_cfg = cfg['optimization']['bootstrap']
            optimized_agent, eval_results = opt.optimize_bootstrap(
                trainset=train,
                valset=val,
                metric=metric,
                max_bootstrapped_demos=opt_cfg['max_bootstrapped_demos'],
                max_labeled_demos=opt_cfg['max_labeled_demos'],
                max_rounds=opt_cfg['max_rounds']
            )

        elif optimizer == "mipro":
            opt_cfg = cfg['optimization']['mipro']
            optimized_agent, eval_results = opt.optimize_mipro(
                trainset=train,
                valset=val,
                metric=metric,
                num_candidates=opt_cfg['num_candidates'],
                init_temperature=opt_cfg['init_temperature'],
                minibatch_size=opt_cfg.get('minibatch_size', None)  # Auto-adjusts if not specified
            )

        elif optimizer == "copro":
            opt_cfg = cfg['optimization']['copro']
            optimized_agent, eval_results = opt.optimize_copro(
                trainset=train,
                valset=val,
                metric=metric,
                depth=opt_cfg['depth'],
                breadth=opt_cfg['breadth']
            )

        else:
            console.print(f"[red]Unknown optimizer: {optimizer}[/red]")
            raise typer.Exit(1)

        optimized_score = eval_results['score']
        improvement = optimized_score - baseline_score

        console.print(f"[green]✓ Optimized score: {optimized_score:.3f}[/green]")
        console.print(f"[green]✓ Improvement: {improvement:+.3f}[/green]")

        # Save the optimized module for inspection
        module_save_path = Path(cfg['output']['experiments_dir']) / f"{experiment_name}_module.json"
        try:
            optimized_agent.save(str(module_save_path))
            console.print(f"[dim]Saved module to: {module_save_path}[/dim]")
        except Exception as e:
            logger.warning(f"Could not save module: {e}")

    except Exception as e:
        console.print(f"[red]Error during optimization: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

    # Step 7: Export prompts
    console.print("\n[bold]Step 7: Exporting optimized prompts...[/bold]")

    exporter = OpenCodeExporter(output_dir=cfg['output']['prompts_dir'])

    agent_name = cfg['data']['agent_filter'] or 'build'
    model_name = student_cfg['model']

    try:
        export_paths = exporter.export_all_formats(
            optimized_module=optimized_agent,
            agent_name=agent_name,
            model_name=model_name,
            baseline_score=baseline_score,
            optimized_score=optimized_score
        )

        for format_name, path in export_paths.items():
            console.print(f"[green]✓ {format_name}: {path}[/green]")

        # Create usage guide
        if cfg['output']['create_usage_guide']:
            guide_path = exporter.create_usage_guide(agent_name, model_name, export_paths)
            console.print(f"[green]✓ Usage guide: {guide_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error exporting prompts: {e}[/red]")
        raise typer.Exit(1)

    # Step 8: Save experiment results
    tracker = ExperimentTracker(cfg['output']['experiments_dir'])
    tracker.log_experiment(
        name=experiment_name,
        optimizer_type=optimizer,
        baseline_score=baseline_score,
        optimized_score=optimized_score,
        config=opt_cfg if 'opt_cfg' in locals() else {},
        model=model_name
    )
    tracker.save_results()

    # Print summary
    console.print("\n[bold green]Optimization Complete![/bold green]")
    console.print()

    table = Table(title="Results Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Baseline Score", f"{baseline_score:.3f}")
    table.add_row("Optimized Score", f"{optimized_score:.3f}")
    table.add_row("Improvement", f"{improvement:+.3f}")
    table.add_row("Training Examples", str(len(train)))
    table.add_row("Validation Examples", str(len(val)))

    console.print(table)
    console.print()
    console.print(f"[yellow]Next steps:[/yellow]")
    console.print(f"1. Review the exported prompts in {cfg['output']['prompts_dir']}")
    console.print(f"2. See the usage guide for integration instructions")
    console.print(f"3. Test the optimized prompt with OpenCode")


@app.command()
def clear_cache():
    """Clear DSPy cache to force fresh predictions on next run."""
    cache_dir = Path.home() / ".dspy_cache"

    if not cache_dir.exists():
        console.print("[yellow]Cache directory does not exist.[/yellow]")
        return

    try:
        # Count files before deletion
        file_count = sum(1 for _ in cache_dir.rglob("*.db"))

        # Clear all .db files but preserve directory structure
        for db_file in cache_dir.rglob("*.db"):
            db_file.unlink()

        console.print(f"[green]✓ Cleared {file_count} cached predictions from {cache_dir}[/green]")
        console.print("[dim]Directory structure preserved (DSPy requires 000-015 subdirectories)[/dim]")
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


@app.command()
def validate(
    config: Path = typer.Option("config/default.yaml", help="Configuration file path"),
):
    """Validate configuration and data."""

    cfg = load_config(str(config))

    console.print("[bold blue]Validating Configuration[/bold blue]")
    console.print()

    # Check session logs directory
    session_logs_dir = Path(cfg['data']['session_logs_dir'])
    if session_logs_dir.exists():
        json_files = list(session_logs_dir.glob("*.json"))
        console.print(f"[green]✓ Session logs directory: {session_logs_dir}[/green]")
        console.print(f"  Found {len(json_files)} JSON files")
    else:
        console.print(f"[red]✗ Session logs directory not found: {session_logs_dir}[/red]")

    # Check OpenCode source path
    opencode_path = Path(cfg['opencode']['source_path'])
    if opencode_path.exists():
        console.print(f"[green]✓ OpenCode source: {opencode_path}[/green]")
    else:
        console.print(f"[yellow]⚠ OpenCode source not found: {opencode_path}[/yellow]")
        console.print(f"  Will use default templates")

    console.print()

    # Check teacher model configuration
    teacher_cfg = cfg['models']['teacher']
    console.print("[bold]Teacher Model Configuration:[/bold]")
    console.print(f"  Provider: {teacher_cfg.get('provider', 'not set')}")
    console.print(f"  Model: {teacher_cfg['model']}")
    console.print(f"  API Base: {teacher_cfg.get('api_base', 'default')}")

    teacher_key_env = teacher_cfg.get('api_key_env')
    if teacher_key_env:
        if os.getenv(teacher_key_env):
            console.print(f"  API Key: [green]✓ Set ({teacher_key_env})[/green]")
        else:
            console.print(f"  API Key: [yellow]⚠ Not set ({teacher_key_env})[/yellow]")
    else:
        console.print(f"  API Key: Not required")

    console.print()

    # Check student model configuration
    student_cfg = cfg['models']['student']
    console.print("[bold]Student Model Configuration:[/bold]")
    console.print(f"  Provider: {student_cfg.get('provider', 'not set')}")
    console.print(f"  Model: {student_cfg['model']}")
    console.print(f"  API Base: {student_cfg.get('api_base', 'default')}")

    student_key_env = student_cfg.get('api_key_env')
    if student_key_env:
        if os.getenv(student_key_env):
            console.print(f"  API Key: [green]✓ Set ({student_key_env})[/green]")
        else:
            console.print(f"  API Key: [yellow]⚠ Not set ({student_key_env})[/yellow]")
    else:
        console.print(f"  API Key: Not required")

    console.print()
    console.print("[green]Validation complete![/green]")


if __name__ == "__main__":
    app()
