# Quick Start Guide

Get started with DSPy OpenCode Prompt Optimization in 5 minutes.

## Prerequisites

- Python 3.10+ with DSPy installed
- OpenCode session logs (you have 19 samples in `data/`)
- (Optional) Ollama for local model testing

## Installation

```bash
cd /home/alan/opencode-dspy/dspy-trainingv2

# Install dependencies
micromamba run -n dspy-training pip install -r requirements.txt
```

## Verify Installation

```bash
# Run validation
micromamba run -n dspy-training python cli.py validate

# Run tests
micromamba run -n dspy-training python test_pipeline.py
```

Expected output:
```
✓ PASS: Data Pipeline
✓ PASS: Context Builder
✓ PASS: Metrics
✓ PASS: Agent Module
✓ PASS: Exporter
✓ All tests passed!
```

## Run Your First Optimization

### Option 1: Local Model (Recommended for Testing)

```bash
# Start Ollama (in another terminal)
ollama serve

# Pull a model
ollama pull qwen2.5-coder:32b

# Run optimization
micromamba run -n dspy-training python cli.py train \
  --experiment-name my-first-optimization
```

### Option 2: Cloud Models

The default configuration now uses OpenAI for the teacher model. You can also use Anthropic or other providers.

**Using OpenAI (Default):**

```bash
# Set API key
export OPENAI_API_KEY=your_key_here

# Run optimization
micromamba run -n dspy-training python cli.py train
```

**Using Anthropic:**

```bash
# Set API key
export ANTHROPIC_API_KEY=your_key_here

# Edit config/default.yaml to change provider to "anthropic"
# Then run:
micromamba run -n dspy-training python cli.py train
```

**Using OpenAI-Compatible APIs (Together AI, vLLM, etc.):**

```bash
# Set API key (if needed)
export TOGETHER_API_KEY=your_key_here

# Use the example config
micromamba run -n dspy-training python cli.py train \
  --config config/openai-compatible-example.yaml
```

## What Happens During Optimization

1. **Load Data** (10 sec)
   - Parses 19 session logs
   - Filters successful examples
   - Converts to DSPy format

2. **Evaluate Baseline** (30-60 sec)
   - Tests unoptimized agent
   - Establishes baseline score

3. **Run Optimization** (5-15 min)
   - BootstrapFewShot generates demonstrations
   - Teacher model creates candidate prompts
   - Student model evaluates quality

4. **Export Results** (5 sec)
   - Saves optimized prompts
   - Generates integration guide

## Expected Output

```
DSPy OpenCode Prompt Optimizer

Experiment: my-first-optimization
Optimizer: bootstrap

Step 1: Loading session logs...
✓ Loaded 19 examples

Step 2: Converting to DSPy format...
✓ Converted 19 examples to DSPy format

Step 3: Splitting data...
✓ Train: 13, Val: 3, Test: 3

Step 4: Setting up models...
✓ Teacher: claude-sonnet-4-5
✓ Student: qwen2.5-coder:32b

Step 5: Evaluating baseline...
✓ Baseline score: 0.650

Step 6: Running bootstrap optimization...
This may take a while...
✓ Optimized score: 0.720
✓ Improvement: +0.070

Step 7: Exporting optimized prompts...
✓ agent_config: outputs/prompts/opencode-build-qwen2.5-coder:32b.jsonc
✓ custom_instructions: outputs/prompts/OPTIMIZED_BUILD.md
✓ prompt_template: outputs/prompts/qwen2.5-coder:32b-optimized.txt
✓ Usage guide: outputs/prompts/USAGE_GUIDE_build.md

Optimization Complete!

┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric              ┃ Value   ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Baseline Score      │ 0.650   │
│ Optimized Score     │ 0.720   │
│ Improvement         │ +0.070  │
│ Training Examples   │ 13      │
│ Validation Examples │ 3       │
└─────────────────────┴─────────┘

Next steps:
1. Review the exported prompts in outputs/prompts
2. See the usage guide for integration instructions
3. Test the optimized prompt with OpenCode
```

## Use the Optimized Prompt

### Quick Test (Recommended)

1. Review the agent config:
```bash
cat outputs/prompts/opencode-build-*.jsonc
```

2. Copy the `prompt` value to your OpenCode config:
```jsonc
{
  "agent": {
    "build": {
      "prompt": "Your optimized prompt here..."
    }
  }
}
```

3. Test with OpenCode:
```bash
opencode "Create a hello world script"
```

### Full Integration

See `outputs/prompts/USAGE_GUIDE_build.md` for detailed integration instructions.

## Understanding Results

### Baseline Score
The performance of the default OpenCode prompt on your validation set (0-1 scale).

### Optimized Score
The performance after DSPy optimization.

### Improvement
The difference. Positive means optimization helped!

### Typical Results

With 19 examples:
- Improvement: +0.05 to +0.15
- Enough to demonstrate the system works
- Need more data for significant gains

With 50+ examples:
- Improvement: +0.15 to +0.40
- Substantial performance gains
- Production-ready prompts

## Troubleshooting

### "No examples found"
Lower the quality threshold in `config/default.yaml`:
```yaml
data:
  min_correctness: 0.5  # Lower from 0.8
```

### "API key error"
For local testing, use Ollama (no API key needed):
```yaml
models:
  student:
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

### "Optimization too slow"
Reduce the training set or use fewer rounds:
```yaml
optimization:
  bootstrap:
    max_rounds: 1  # Use 1 round instead of multiple
```

## Next Steps

1. **Collect more data**: Run OpenCode on real tasks, copy successful sessions to `data/`
2. **Try different optimizers**: `--optimizer copro` or `--optimizer mipro`
3. **Experiment with settings**: Edit `config/default.yaml`
4. **Compare models**: Test different student models

## Example Commands

```bash
# Full training with custom settings
micromamba run -n dspy-training python cli.py train \
  --config config/default.yaml \
  --experiment-name exp-qwen-32b \
  --optimizer bootstrap \
  --output-dir ./my-outputs

# Quick validation
micromamba run -n dspy-training python cli.py validate

# Run tests
micromamba run -n dspy-training python test_pipeline.py
```

## Getting Help

1. **Check the README**: Comprehensive documentation
2. **Review test output**: `test_pipeline.py` shows what works
3. **Examine sample logs**: `data/*.json` shows expected format
4. **Read the plan**: `OPENCODE_DSPY_PLAN.md` explains architecture

## Success Criteria

✅ Tests pass
✅ Validation succeeds
✅ Optimization completes
✅ Improvement > 0
✅ Prompts exported

If all ✅, you're ready to use the system!
