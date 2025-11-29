# DSPy-Based Prompt Optimization for OpenCode

A system to optimize agent prompts for OpenCode using DSPy, targeting improved performance with smaller/local models.

## Overview

This system ingests session logs from the OpenCode session logger plugin, extracts training examples with ground-truth evaluations, and uses DSPy's optimization primitives to generate prompts that work more effectively with constrained models.

### Key Features

- **Automated prompt optimization** using DSPy's BootstrapFewShot, MIPROv2, and COPRO algorithms
- **Session log integration** - learns from real OpenCode usage patterns
- **Multiple export formats** - agent configs, custom instructions, and prompt templates
- **Quality metrics** - evaluates tool selection, reasoning quality, and task completion
- **Teacher-student setup** - uses strong models to optimize prompts for smaller models

## Quick Start

### 1. Installation

```bash
# Clone/navigate to the repository
cd dspy-trainingv2

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Configuration

Edit `config/default.yaml` to configure:

- Session logs directory
- Teacher model (for optimization)
- Student model (target model to optimize for)
- API keys and endpoints
- Optimization settings

```yaml
data:
  session_logs_dir: "./data"  # Your session logs

models:
  teacher:
    model: "claude-sonnet-4-5"
    api_key_env: "ANTHROPIC_API_KEY"

  student:
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

### 3. Collect Session Logs

Use the OpenCode session logger plugin to generate training data:

1. Install the session logger plugin in OpenCode
2. Complete coding tasks with OpenCode
3. Session logs will be saved as JSON files
4. Copy successful sessions to `./data/`

### 4. Validate Setup

```bash
python cli.py validate
```

### 5. Test the Pipeline

```bash
python test_pipeline.py
```

### 6. Run Optimization

```bash
python cli.py train --experiment-name my-first-optimization
```

This will:
1. Load and parse session logs
2. Convert to DSPy format
3. Split into train/val/test sets
4. Evaluate baseline agent
5. Run optimization (BootstrapFewShot by default)
6. Export optimized prompts
7. Generate usage guide

### 7. Use Optimized Prompts

After optimization, you'll find:

- **`outputs/prompts/opencode-*.jsonc`** - Agent configuration to add to `opencode.jsonc`
- **`outputs/prompts/OPTIMIZED_*.md`** - Custom instructions file
- **`outputs/prompts/*-optimized.txt`** - Full prompt template
- **`outputs/prompts/USAGE_GUIDE_*.md`** - Integration instructions

See the usage guide for detailed integration steps.

## Using Different LLM Providers

The system supports multiple providers for both teacher and student models. The default configuration uses OpenAI for the teacher and Ollama for the student, but you can easily switch.

### OpenAI (Default Teacher)

```yaml
models:
  teacher:
    provider: "openai"
    model: "gpt-4o"  # or gpt-4-turbo, gpt-4o-mini
    api_key_env: "OPENAI_API_KEY"
```

Setup:
```bash
export OPENAI_API_KEY=your_key_here
```

### Anthropic

```yaml
models:
  teacher:
    provider: "anthropic"
    model: "claude-sonnet-4-5"  # or claude-opus-4
    api_key_env: "ANTHROPIC_API_KEY"
```

Setup:
```bash
export ANTHROPIC_API_KEY=your_key_here
```

### OpenAI-Compatible APIs

Works with Together AI, vLLM, OpenRouter, LM Studio, and other OpenAI-compatible endpoints:

```yaml
models:
  teacher:
    provider: "openai-compatible"
    model: "meta-llama/Meta-Llama-3.1-70B-Instruct"
    api_base: "https://api.together.xyz/v1"
    api_key_env: "TOGETHER_API_KEY"
```

**Popular OpenAI-compatible providers:**

- **Together AI**: `https://api.together.xyz/v1`
- **OpenRouter**: `https://openrouter.ai/api/v1`
- **vLLM (local)**: `http://localhost:8000/v1`
- **LM Studio (local)**: `http://localhost:1234/v1`

### Local Ollama (Default Student)

```yaml
models:
  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
    api_key_env: null  # No API key needed
```

Setup:
```bash
ollama serve
ollama pull qwen2.5-coder:32b
```

### Example Configurations

We provide example config files for common setups:

- **`config/default.yaml`** - OpenAI teacher + Ollama student
- **`config/openai-example.yaml`** - Both OpenAI models
- **`config/openai-compatible-example.yaml`** - Together AI/vLLM teacher + Ollama student

Use them with:
```bash
python cli.py train --config config/openai-example.yaml
```

## Project Structure

```
dspy-trainingv2/
├── src/
│   ├── data/
│   │   ├── session_parser.py      # Parse OpenCode session logs
│   │   └── example_builder.py     # Convert to DSPy format
│   ├── context/
│   │   ├── prompt_templates.py    # OpenCode prompt templates
│   │   └── context_builder.py     # Reconstruct OpenCode prompts
│   ├── dspy_modules/
│   │   ├── signatures.py          # DSPy task signatures
│   │   └── code_agent.py          # OpenCodeAgent module
│   ├── evaluation/
│   │   └── metrics.py             # Evaluation metrics
│   ├── optimization/
│   │   └── optimizer.py           # DSPy optimization pipeline
│   └── export/
│       └── opencode_exporter.py   # Export optimized prompts
├── config/
│   └── default.yaml               # Configuration
├── data/                          # Session logs go here
├── cli.py                         # Command-line interface
├── test_pipeline.py               # Pipeline validation
├── requirements.txt               # Dependencies
└── README.md                      # This file
```

## How It Works

### 1. Data Pipeline

The system parses OpenCode session logs (JSON format) and extracts:

- User task/request
- Environment context (files, git status, etc.)
- Tool action sequence
- Evaluation metrics (correctness, efficiency, etc.)

These are converted to DSPy Examples with input/output pairs suitable for optimization.

### 2. Optimization

DSPy optimizers use a **teacher-student** approach:

- **Teacher model** (e.g., Claude Sonnet 4.5): Generates candidate prompts
- **Student model** (e.g., Qwen 2.5 Coder 32B): Target model being optimized

Three optimization strategies are supported:

- **BootstrapFewShot**: Generates few-shot demonstrations that improve smaller model performance
- **MIPROv2**: Multi-prompt instruction optimization for finding optimal phrasing
- **COPRO**: Coordinate-ascent refinement of prompt components

### 3. Evaluation Metrics

The composite metric evaluates:

- **Tool validity** (3x weight): Can the agent select valid tools?
- **Plan coherence** (2x weight): Does the plan match expected actions?
- **First action match** (2x weight): Is the first action correct?
- **Reasoning quality** (1x weight): Does reasoning mention relevant context?
- **Efficiency** (1x weight): Is the reasoning concise?

### 4. Export & Integration

Optimized prompts are exported in three formats:

1. **Agent config**: Add to `opencode.jsonc` under `agent.<name>.prompt`
2. **Custom instructions**: Reference in `opencode.jsonc` under `instructions`
3. **Prompt template**: Replace model-specific template files

## CLI Reference

### Train

```bash
python cli.py train [OPTIONS]
```

Options:
- `--config PATH`: Configuration file (default: `config/default.yaml`)
- `--experiment-name NAME`: Experiment name (default: auto-generated)
- `--optimizer {bootstrap|mipro|copro}`: Optimizer type (default: from config)
- `--output-dir PATH`: Output directory (default: from config)

### Validate

```bash
python cli.py validate [OPTIONS]
```

Validates configuration and checks that required files/directories exist.

## Configuration Reference

See `config/default.yaml` for full configuration options. Key sections:

### Data

```yaml
data:
  session_logs_dir: "./data"
  min_correctness: 0.8        # Minimum quality threshold
  min_efficiency: 0.3
  require_success: true       # Only use successful sessions
  agent_filter: null          # Filter to specific agent (build/plan)
  train_split: 0.7
  val_split: 0.15
  test_split: 0.15
```

### Models

The system supports multiple LLM providers for both teacher and student models:

**Supported Providers:**
- `openai` - OpenAI (GPT-4, GPT-4o, etc.)
- `anthropic` - Anthropic (Claude models)
- `openai-compatible` - Any OpenAI-compatible API (Together AI, vLLM, OpenRouter, etc.)
- `ollama` - Local Ollama models

**Example configurations:**

```yaml
# OpenAI teacher + Ollama student (default)
models:
  teacher:
    provider: "openai"
    model: "gpt-4o"
    api_key_env: "OPENAI_API_KEY"

  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

```yaml
# Anthropic teacher + Ollama student
models:
  teacher:
    provider: "anthropic"
    model: "claude-sonnet-4-5"
    api_key_env: "ANTHROPIC_API_KEY"

  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

```yaml
# OpenAI-compatible (Together AI) teacher + Ollama student
models:
  teacher:
    provider: "openai-compatible"
    model: "meta-llama/Meta-Llama-3.1-70B-Instruct"
    api_base: "https://api.together.xyz/v1"
    api_key_env: "TOGETHER_API_KEY"

  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

### Optimization

```yaml
optimization:
  default_optimizer: "bootstrap"

  bootstrap:
    max_bootstrapped_demos: 4
    max_labeled_demos: 4
    max_rounds: 1

  copro:
    depth: 3
    breadth: 10
```

## Expected Results

With sufficient training data (50+ successful sessions), you should expect:

- **15-40% improvement** in task completion rate for smaller models
- **Reduced token usage** through more focused reasoning
- **Better tool selection** on first attempt
- **Prompts that transfer** across similar model families

## Troubleshooting

For comprehensive troubleshooting guidance, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

### Quick Solutions

**No examples found**:
- Lower `min_correctness` in `config/default.yaml`
- Check `data/` directory has .json files
- Set `require_success: false` temporarily

**API key errors**:
- Set environment variables: `export OPENAI_API_KEY=your_key`
- Use `.env` file in project root
- For Ollama: ensure server is running with `ollama serve`

**Optimization too slow**:
- Reduce training set size in config
- Use `--optimizer bootstrap` (fastest)
- Try smaller teacher model

**Low improvement scores**:
- Need 50+ training examples for best results
- Try different optimizer types
- Ensure high-quality training data

**Cache behavior**:
- Use `python cli.py clear-cache` to get fresh results
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#caching-issues) for details

For detailed solutions to these and other issues, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

## Advanced Usage

### Custom Metrics

Define custom metrics in `src/evaluation/metrics.py`:

```python
def my_custom_metric(example, prediction, trace=None) -> float:
    # Your evaluation logic
    return score  # 0.0 to 1.0
```

Then reference in your training code.

### Multiple Model Optimization

Run optimization for multiple target models:

```bash
for model in qwen2.5-coder:32b deepseek-coder-v2:16b codellama:34b; do
  python cli.py train --experiment-name opt-$model --model $model
done
```

### Hyperparameter Tuning

Experiment with different optimizer settings:

```bash
# Try different demo counts
python cli.py train --config config/4demos.yaml
python cli.py train --config config/8demos.yaml

# Try different optimizers
python cli.py train --optimizer bootstrap
python cli.py train --optimizer copro
```

## Contributing

This is a research project for optimizing OpenCode prompts. Contributions welcome:

- Additional metrics
- New optimization strategies
- Better prompt extraction methods
- Integration improvements

## License

See LICENSE file.

## Citation

If you use this work, please cite:

```
DSPy-Based Prompt Optimization for OpenCode
https://github.com/your-repo/opencode-dspy
```

Also cite the original DSPy paper:
```
Khattab, O., et al. (2023). DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines.
```
