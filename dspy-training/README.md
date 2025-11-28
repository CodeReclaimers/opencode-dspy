# DSPy Training Infrastructure for OpenCode

A complete DSPy training pipeline that optimizes prompts for OpenCode agents using real session data.

## Overview

This project provides a comprehensive infrastructure to:
1. Load OpenCode session logs from JSON files
2. Convert them to DSPy Example objects
3. Partition data into train/validation sets
4. Define evaluation metrics
5. Run MIPROv2 optimization
6. Export optimized prompts ready for OpenCode

## Features

- **Flexible Data Loading**: Automatically loads and validates OpenCode session logs
- **Smart Conversion**: Converts complex session data to DSPy-compatible format
- **Multiple Optimizers**: Supports MIPROv2, COPRO, and BootstrapFewShot
- **Custom Metrics**: Evaluates based on success rate, efficiency, and correctness
- **OpenCode Integration**: Exports prompts in OpenCode-ready markdown format
- **Production Ready**: Comprehensive error handling, logging, and validation

## Project Structure

```
dspy-training/
├── data/
│   ├── raw/              # Put your JSON session logs here
│   ├── processed/        # Processed DSPy examples
│   └── splits/           # Train/val splits
├── src/
│   ├── __init__.py
│   ├── data_loader.py    # Load and parse JSON files
│   ├── dspy_converter.py # Convert to DSPy examples
│   ├── metrics.py        # Evaluation metrics
│   ├── optimizer.py      # Run DSPy optimization
│   └── prompt_exporter.py # Export to OpenCode format
├── outputs/
│   ├── prompts/          # Optimized prompts
│   └── logs/             # Training logs
├── requirements.txt
├── config.yaml           # Configuration
└── run_training.py       # Main script
```

## Installation

### Prerequisites

- Python 3.8 or higher
- Ollama (if using local models)
- API keys for teacher models (e.g., Anthropic, OpenAI)

### Setup

1. Install dependencies:

```bash
make install
# or manually:
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
cp .env.example .env
# Edit .env and add your API keys
```

3. Review and customize `config.yaml` for your needs

## Preparing Data

### Session Log Format

OpenCode session logs should be JSON files with this structure:

```json
{
  "session": "session-id",
  "generated": "2024-01-01T00:00:00Z",
  "totalExamples": 1,
  "outcome": {
    "success": true,
    "taskCompleted": true,
    "metrics": {},
    "evaluation": {}
  },
  "examples": [
    {
      "input": {
        "task": "Add a new feature",
        "context": {}
      },
      "actions": [
        {
          "step": 1,
          "tool": "read",
          "args": {"filePath": "/path/to/file"},
          "timestamp": "2024-01-01T00:00:00Z",
          "result": "...",
          "success": true
        }
      ],
      "output": {
        "response": "Feature added successfully"
      },
      "outcome": {
        "success": true,
        "taskCompleted": true,
        "metrics": {}
      },
      "agent": {},
      "metadata": {}
    }
  ]
}
```

### Adding Data

1. Place your JSON session logs in `data/raw/`
2. Run validation:

```bash
make prepare-data
```

### Data Requirements

- Minimum 10 examples (configurable in `config.yaml`)
- At least one successful session (if `require_success: true`)
- Valid JSON format with required fields

## Running Training

### Quick Start

```bash
make train
```

### Manual Execution

```bash
python run_training.py
```

### What Happens During Training

1. **Data Loading**: Loads and validates all JSON files from `data/raw/`
2. **Filtering**: Optionally filters to successful sessions only
3. **Conversion**: Converts sessions to DSPy Example format
4. **Partitioning**: Splits data (default: 20% train, 80% validation)
5. **Optimization**: Runs DSPy optimizer (MIPROv2 by default)
6. **Evaluation**: Evaluates optimized agent on validation set
7. **Export**: Saves optimized prompt to `outputs/prompts/`

### Training Output

The pipeline produces:
- `outputs/prompts/<model>-optimized.md`: OpenCode-ready prompt file
- `data/processed/examples.json`: Processed DSPy examples
- Training logs with detailed progress

## Configuration

Edit `config.yaml` to customize:

### Data Settings

```yaml
data:
  raw_dir: "./data/raw"
  processed_dir: "./data/processed"
  train_split: 0.2          # 20% for training
  val_split: 0.8            # 80% for validation
  min_examples: 10          # Minimum required examples
  require_success: true     # Only use successful sessions
```

### Model Settings

```yaml
models:
  # Model you're optimizing prompts for
  target:
    provider: "ollama"
    model: "qwen2.5-coder:7b"
    temperature: 0.0
    
  # Model used to generate optimized prompts
  teacher:
    provider: "anthropic"
    model: "claude-sonnet-4-5"
    api_key_env: "ANTHROPIC_API_KEY"
```

### Optimization Settings

```yaml
optimization:
  optimizer: "MIPROv2"      # Options: MIPROv2, COPRO, BootstrapFewShot
  auto_mode: "light"        # Options: light, medium, heavy
  num_trials: 20            # Number of optimization iterations
  max_bootstrapped_demos: 3 # Few-shot examples to include
  max_labeled_demos: 2
  
  # How to weight different aspects
  metric_weights:
    success: 0.5            # Task completion success
    efficiency: 0.3         # Number of tool calls
    correctness: 0.2        # Response quality
```

## Using Optimized Prompts

After training completes:

1. **Review the prompt**:
   ```bash
   cat outputs/prompts/<model>-optimized.md
   ```

2. **Copy to OpenCode**:
   ```bash
   cp outputs/prompts/<model>-optimized.md ~/.config/opencode/agent/
   ```

3. **Update OpenCode config** (`~/.config/opencode/opencode.json`):
   ```json
   {
     "agent": "<model>-optimized"
   }
   ```

4. **Test the optimized agent**:
   ```bash
   opencode --agent <model>-optimized
   ```

## Advanced Usage

### Custom Metrics

Create your own metric in `src/metrics.py`:

```python
def my_custom_metric(example, prediction, trace=None):
    # Your evaluation logic
    return score  # 0.0 to 1.0
```

Update `run_training.py` to use it:

```python
metric = my_custom_metric
```

### Different Optimizers

Change the optimizer in `config.yaml`:

```yaml
optimization:
  optimizer: "BootstrapFewShot"  # or "COPRO"
```

### Multiple Models

Run training for different target models by modifying `config.yaml` and running again:

```yaml
models:
  target:
    model: "llama3:8b"  # Different model
```

## Troubleshooting

### "No session logs found"

- Ensure JSON files are in `data/raw/`
- Check file permissions
- Verify JSON format is valid

### "No successful sessions found"

- Set `require_success: false` in config.yaml
- Or add more successful session logs

### "Failed to convert examples"

- Check that session logs match the expected format
- Review error messages in console
- Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`

### Import Errors

- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Activate your virtual environment
- Check Python version (3.8+)

### API Key Issues

- Verify `.env` file exists and contains valid keys
- Check that `api_key_env` in config.yaml matches environment variable name
- Ensure API key has sufficient credits

## Development

### Running Tests

```bash
make test
```

### Code Structure

- `src/data_loader.py`: Handles JSON loading and validation using Pydantic
- `src/dspy_converter.py`: Converts sessions to DSPy Examples
- `src/metrics.py`: Evaluation metrics for optimization
- `src/optimizer.py`: DSPy optimization logic
- `src/prompt_exporter.py`: Exports to OpenCode format
- `run_training.py`: Main orchestration script

### Adding Features

1. Create feature branch
2. Implement changes
3. Add tests
4. Update documentation
5. Submit pull request

## Performance Tips

1. **Start Small**: Begin with `auto_mode: "light"` and `num_trials: 10`
2. **Filter Data**: Use `require_success: true` for better results
3. **Increase Gradually**: Scale up trials as you validate the approach
4. **Monitor Costs**: Teacher model calls can add up with heavy optimization
5. **Cache Results**: Processed examples are saved to avoid reprocessing

## Best Practices

1. **Data Quality**: More high-quality examples > many low-quality ones
2. **Balanced Splits**: DSPy recommends 20/80 train/val for prompt optimization
3. **Metric Weights**: Adjust based on what matters most for your use case
4. **Iterative Approach**: Start with small changes, validate, then scale
5. **Version Control**: Track config changes and results

## Examples

### Training for a Local Model

```yaml
models:
  target:
    provider: "ollama"
    model: "codellama:7b"
    temperature: 0.0
```

### Training for Cloud API

```yaml
models:
  target:
    provider: "openai"
    model: "gpt-4"
    temperature: 0.0
    api_key_env: "OPENAI_API_KEY"
```

### Quick Iteration Mode

```yaml
optimization:
  auto_mode: "light"
  num_trials: 5
data:
  min_examples: 5
```

## Contributing

Contributions welcome! Please:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Keep commits focused and clear

## License

MIT License - see LICENSE file

## Support

- Issues: Open a GitHub issue
- Discussions: Use GitHub Discussions
- Documentation: Check this README first

## Acknowledgments

- Built on [DSPy](https://github.com/stanfordnlp/dspy)
- Designed for [OpenCode](https://opencode.ai)
- Inspired by the LLM optimization community
