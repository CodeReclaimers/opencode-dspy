# DSPy Training Quick Start Guide

Get started with DSPy training for OpenCode in 5 minutes!

## Prerequisites

- Python 3.8+
- OpenCode session logs (JSON format)
- API key for teacher model (e.g., Anthropic Claude)

## Step 1: Install Dependencies

```bash
cd dspy-training
make install
```

Or manually:

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```bash
# Edit .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Step 3: Add Training Data

Place your OpenCode session log JSON files in `data/raw/`:

```bash
cp /path/to/your/session-logs/*.json data/raw/
```

Don't have session logs yet? See `data/raw/example_session.json` for the expected format.

## Step 4: Validate Data

```bash
make prepare-data
```

This will:
- Load all JSON files from `data/raw/`
- Validate the format
- Show statistics about your data

You should see output like:
```
✓ Found 15 valid session logs
✓ 12 successful sessions
✓ 45 total examples
```

## Step 5: Review Configuration

Edit `config.yaml` to customize:

```yaml
data:
  min_examples: 10        # Minimum examples needed
  require_success: true   # Only use successful sessions

models:
  target:
    model: "qwen2.5-coder:7b"  # Model to optimize for
  teacher:
    model: "claude-sonnet-4-5"  # Model to generate prompts

optimization:
  optimizer: "MIPROv2"
  auto_mode: "light"      # Start with light mode
  num_trials: 20          # Number of optimization iterations
```

## Step 6: Run Training

```bash
make train
```

Or:

```bash
python run_training.py
```

This will:
1. Load and convert your session logs
2. Split into train/validation sets (20/80)
3. Run DSPy optimization
4. Evaluate the optimized agent
5. Export the optimized prompt

Training time depends on:
- Number of examples
- `auto_mode` setting (light/medium/heavy)
- `num_trials` setting
- Teacher model speed

Expected times:
- Light mode, 20 trials, 20 examples: 5-10 minutes
- Medium mode, 50 trials, 50 examples: 30-60 minutes
- Heavy mode, 100 trials, 100 examples: 2-4 hours

## Step 7: Use the Optimized Prompt

After training completes, you'll see:

```
Training complete!
Optimized prompt saved to: outputs/prompts/qwen2.5-coder-7b-optimized.md
Validation score: 85.50%
```

Copy to OpenCode:

```bash
cp outputs/prompts/qwen2.5-coder-7b-optimized.md ~/.config/opencode/agent/
```

Update your OpenCode config (`~/.config/opencode/opencode.json`):

```json
{
  "agent": "qwen2.5-coder-7b-optimized"
}
```

Test it:

```bash
opencode --agent qwen2.5-coder-7b-optimized
```

## Troubleshooting

### "No session logs found"

Make sure JSON files are in `data/raw/` directory:
```bash
ls -la data/raw/*.json
```

### "No successful sessions found"

Either:
1. Add more successful session logs
2. Set `require_success: false` in config.yaml

### "Not enough examples"

You need at least 10 examples (by default). Either:
1. Collect more session logs
2. Lower `min_examples` in config.yaml (not recommended)

### "Import errors"

Make sure dependencies are installed:
```bash
pip install -r requirements.txt
```

### "API key errors"

Check that:
1. `.env` file exists
2. Contains the correct API key
3. `api_key_env` in config.yaml matches the variable name in `.env`

## Next Steps

1. **Iterate**: Try different optimization settings
2. **Collect More Data**: More examples = better optimization
3. **Compare**: Test optimized vs. baseline prompts
4. **Share**: Contribute optimized prompts back to the community

## Tips for Best Results

1. **Start Small**: Begin with light mode and fewer trials
2. **Quality over Quantity**: 20 high-quality examples > 100 low-quality ones
3. **Filter Failures**: Set `require_success: true` for better training
4. **Adjust Weights**: Customize metric weights based on your priorities
5. **Monitor Costs**: Keep an eye on teacher model API usage

## Advanced Usage

See the full [README.md](README.md) for:
- Custom metrics
- Different optimizers
- Multiple model training
- Development guidelines

## Getting Help

- Check [README.md](README.md) for detailed documentation
- Review example session log: `data/raw/example_session.json`
- Open an issue on GitHub
- Join the OpenCode community

Happy training!
