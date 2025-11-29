# Troubleshooting Guide

This guide covers common issues and solutions encountered during DSPy prompt optimization.

## Quick Reference

| Issue | Solution | Section |
|-------|----------|---------|
| No examples found | Lower quality thresholds | [Data Issues](#data-issues) |
| API key errors | Check environment variables | [API Authentication](#api-authentication) |
| LiteLLM provider errors | Check provider configuration | [Model Configuration](#model-configuration) |
| Optimization too slow | Reduce dataset size | [Performance](#performance-issues) |
| Low improvement scores | Need more training data | [Results](#low-improvement-scores) |
| Cache behavior | Clear cache between runs | [Caching](#caching-issues) |

## Data Issues

### No Training Examples Found

**Symptoms:**
```
No training examples found
Loaded 0 examples
```

**Solutions:**

1. **Lower quality thresholds** in `config/default.yaml`:
   ```yaml
   data:
     min_correctness: 0.5  # Lower from 0.8
     min_efficiency: 0.3
     require_success: false  # Include failed sessions
   ```

2. **Check data directory**:
   ```bash
   ls -la data/*.json
   # Ensure JSON files exist
   ```

3. **Validate JSON format**:
   ```bash
   python -c "import json; json.load(open('data/session.json'))"
   ```

### Training/Validation Split Errors

**Problem**: Not enough examples for split

**Solution**: Adjust split ratios in config:
```yaml
data:
  train_split: 0.8  # Increase training ratio
  val_split: 0.1
  test_split: 0.1
```

## API Authentication

### OpenAI API Key Errors

**Symptoms:**
```
litellm.AuthenticationError: The api_key client option must be set
```

**Solutions:**

1. **Set environment variable**:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```

2. **Use .env file** (recommended):
   ```bash
   # Create .env file in project root
   echo "OPENAI_API_KEY=sk-..." > .env
   ```

3. **Verify key is loaded**:
   ```bash
   echo $OPENAI_API_KEY
   python cli.py validate
   ```

### Anthropic API Key Errors

**Solution:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Update config to use Anthropic:
```yaml
models:
  teacher:
    provider: "anthropic"
    model: "claude-sonnet-4-5"
    api_key_env: "ANTHROPIC_API_KEY"
```

### Ollama Connection Issues

**Symptoms:**
```
Connection refused: http://localhost:11434
```

**Solutions:**

1. **Start Ollama server**:
   ```bash
   ollama serve
   ```

2. **Pull model**:
   ```bash
   ollama pull qwen2.5-coder:32b
   ```

3. **Verify connection**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

## Model Configuration

### LiteLLM Provider Error (Ollama)

**Symptoms:**
```
litellm.BadRequestError: LLM Provider NOT provided.
You passed model=qwen3-coder:30b
```

**This is automatically fixed** in the latest version. The system now:
- Automatically prefixes Ollama models with `ollama_chat/`
- Adds dummy API key `"ollama-no-key-required"` for LiteLLM compatibility

**If you still encounter this:**
1. Ensure `provider: "ollama"` is set in config
2. Ensure `api_base` points to Ollama: `http://localhost:11434/v1`
3. Check Ollama is running: `ollama list`

### Score Formatting Error

**Symptoms:**
```
unsupported format string passed to EvaluationResult.__format__
```

**This is automatically fixed** in the latest version. The system now properly extracts numeric scores from DSPy evaluation results.

**If you still encounter this**, report it as a bug with your DSPy version:
```bash
pip show dspy-ai
```

### Student Model Evaluation Returning 0

**Symptoms:**
- Baseline score: 0.00
- Optimized score: 0.00
- 0 LLM calls made
- Empty Prediction() objects

**Root causes that were fixed:**

1. **Missing API Key for Ollama** - Fixed by adding dummy key
2. **Module Created Outside Context** - Fixed by creating module inside `dspy.context()`
3. **Cache Pollution** - Fixed by using `temperature=0.001` to bypass cache
4. **Silent Exceptions** - Fixed by using `provide_traceback=True`

**If you still see this:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python cli.py train --experiment-name debug-test
```

## Performance Issues

### Optimization Takes Too Long

**Problem**: Optimization running for hours

**Solutions:**

1. **Reduce training set size**:
   ```yaml
   data:
     train_split: 0.5  # Use less data
   ```

2. **Use fewer optimization rounds**:
   ```yaml
   optimization:
     bootstrap:
       max_rounds: 1
   ```

3. **Switch optimizer**:
   ```bash
   # Bootstrap is fastest
   python cli.py train --optimizer bootstrap

   # MIPRO and COPRO are slower
   ```

4. **Use smaller teacher model**:
   ```yaml
   models:
     teacher:
       model: "gpt-4o-mini"  # Faster than gpt-4o
   ```

### Rate Limiting

**Symptoms:**
```
Rate limit exceeded
Too many requests
```

**Solutions:**

1. **Reduce concurrent requests**:
   ```yaml
   evaluation:
     num_threads: 1  # Reduce from 4
   ```

2. **Add delays** (for OpenAI-compatible providers):
   - Use providers with higher limits (Together AI, OpenRouter)
   - Space out optimization runs

3. **Use local models**:
   - Ollama for student (no rate limits)
   - Local vLLM for teacher

## Results

### Low Improvement Scores

**Problem**: Optimized score barely better than baseline

**Causes and Solutions:**

1. **Not enough training data**
   - Current: <20 examples
   - Target: 50+ examples
   - **Solution**: Collect more high-quality session logs

2. **Low quality training data**
   - Check `min_correctness` threshold
   - Review session log quality
   - **Solution**: Filter for successful sessions only

3. **Wrong optimizer for your use case**
   - Bootstrap: Good for few-shot examples
   - MIPRO: Good for prompt instruction tuning
   - COPRO: Good for iterative refinement
   - **Solution**: Try different optimizers

4. **Student model capability**
   - Very small models (<1B params) may not benefit much
   - **Solution**: Try larger student model (7B-32B range)

5. **Metric not aligned with goals**
   - Default metric may not match your needs
   - **Solution**: Adjust metric weights in config

### Identical Scores on Repeated Runs

**Problem**: Running optimization twice gives identical results

**Cause**: This is **expected behavior** due to caching

**Solution**: See [Caching Issues](#caching-issues) below

## Caching Issues

### Understanding DSPy Caching

DSPy caches teacher model predictions for:
- **Reproducibility**: Same inputs → same outputs
- **Cost savings**: Avoid redundant API calls
- **Speed**: Cached results return instantly

**What gets cached:**
- Teacher model predictions (at temperature=0)
- Based on: exact prompt text + temperature + model name

**What doesn't get cached:**
- Student model evaluations (always use temperature=0.001)

### Instant Completion on Second Run

**Observation**: Second optimization completes in <1 second

**Explanation**: Teacher predictions are cached

**This is normal!** To get fresh demonstrations:

```bash
# Option 1: Clear cache before run
python cli.py clear-cache
python cli.py train --experiment-name fresh-run

# Option 2: Change training data
# Add/remove/modify examples

# Option 3: Use non-zero temperature
# Edit config: teacher.temperature: 0.1
```

### Cache Location

DSPy cache is stored at:
```
~/.dspy_cache/
├── *.db           # SQLite databases with cached predictions
└── *.db-journal   # SQLite journal files
```

### Manual Cache Management

```bash
# View cache size
du -sh ~/.dspy_cache/

# Clear all cache
rm ~/.dspy_cache/*.db

# List cached entries
sqlite3 ~/.dspy_cache/cache.db "SELECT COUNT(*) FROM cache;"
```

## Installation Issues

### DSPy Not Installed

**Symptoms:**
```
ImportError: No module named 'dspy'
```

**Solution:**
```bash
pip install dspy-ai
```

### Dependency Conflicts

**Solution**: Use a fresh environment
```bash
# Create new conda/mamba environment
micromamba create -n dspy-training python=3.10
micromamba activate dspy-training
pip install -r requirements.txt
```

### LiteLLM Version Issues

**Problem**: Certain providers not working

**Solution**: Update LiteLLM
```bash
pip install --upgrade litellm
```

## Export Issues

### Prompts Not Exported

**Problem**: `outputs/prompts/` directory empty

**Check:**
1. Optimization completed successfully
2. No errors in logs
3. Output directory permissions

**Solution:**
```bash
# Check output directory
ls -la outputs/prompts/

# Manually specify output directory
python cli.py train --output-dir ./my-outputs
```

### Integration with OpenCode

**Problem**: Optimized prompt doesn't work in OpenCode

**Solutions:**

1. **Check prompt format**:
   ```bash
   cat outputs/prompts/OPTIMIZED_BUILD.md
   ```

2. **Use correct integration method**:
   - Agent config: Copy from `opencode-*.jsonc`
   - Custom instructions: Use `OPTIMIZED_*.md` file
   - Prompt template: Replace model-specific `.txt` file

3. **Verify OpenCode config syntax**:
   ```bash
   # Test OpenCode config is valid JSON/JSONC
   jsonlint opencode.jsonc
   ```

## Debugging Tips

### Enable Debug Logging

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run with verbose output
python cli.py train --experiment-name debug-run
```

### Check Model Configuration

```bash
# Validate configuration
python cli.py validate

# Should show:
# ✓ Teacher model configured
# ✓ Student model configured
# ✓ API keys loaded
# ✓ Data directory exists
```

### Test Individual Components

```bash
# Test data loading
python -c "from src.data.session_parser import SessionParser; \
           p = SessionParser('./data'); \
           print(f'Loaded {len(p.parse_all())} sessions')"

# Test model connection
python -c "import dspy; \
           lm = dspy.LM('openai/gpt-4o'); \
           print(lm('Say hello'))"
```

### View Training Logs

```bash
# Watch logs in real-time
tail -f outputs/logs/training.log

# Filter for key events
tail -f outputs/logs/training.log | grep -E "(score=|ERROR|Exception)"
```

## Getting Help

If you're still stuck:

1. **Check the README** for comprehensive documentation
2. **Review sample logs** in `data/*.json` for expected format
3. **Run validation**: `python cli.py validate`
4. **Check DSPy docs**: https://dspy-docs.vercel.app
5. **Report issues** with:
   - Python version: `python --version`
   - DSPy version: `pip show dspy-ai`
   - Full error message
   - Configuration file (redact API keys)
   - Debug logs

## Common Error Messages

### "No module named 'dspy'"

**Fix**: `pip install dspy-ai`

### "Failed to configure LM"

**Fix**: Check provider name and API key

### "Connection refused"

**Fix**: Start Ollama server or check API base URL

### "Rate limit exceeded"

**Fix**: Reduce `num_threads` or use local models

### "Database locked"

**Fix**: Clear cache: `python cli.py clear-cache`

### "Invalid API key"

**Fix**: Check environment variables: `echo $OPENAI_API_KEY`

## Success Checklist

Before running optimization, verify:

- [ ] Data directory has .json files
- [ ] Config file is valid YAML
- [ ] API keys are set (for cloud models)
- [ ] Models are accessible (Ollama running for local)
- [ ] Validation passes: `python cli.py validate`
- [ ] Tests pass: `python test_pipeline.py`

If all items are checked, you're ready to run optimization!
