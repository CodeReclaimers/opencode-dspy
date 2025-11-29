# Provider Configuration Guide

This guide explains how to configure different LLM providers for DSPy OpenCode optimization.

## Overview

The system uses a **teacher-student** setup:
- **Teacher Model**: A strong model (GPT-4, Claude, etc.) that generates optimization candidates
- **Student Model**: Your target model (often smaller/local) that you want to optimize for

Both can use different providers based on your needs and available resources.

## Supported Providers

| Provider | Description | Use Case |
|----------|-------------|----------|
| `openai` | OpenAI API (GPT-4, GPT-4o, etc.) | High-quality teacher, cloud student |
| `anthropic` | Anthropic API (Claude models) | High-quality teacher |
| `openai-compatible` | Any OpenAI-compatible endpoint | Together AI, vLLM, OpenRouter, etc. |
| `ollama` | Local Ollama instance | Local student models |

## Configuration Examples

### 1. OpenAI Teacher + Ollama Student (Default)

**Best for**: Users with OpenAI API access wanting to optimize local models

**Setup:**
```bash
export OPENAI_API_KEY=sk-...
ollama serve
ollama pull qwen2.5-coder:32b
```

**Config (`config/default.yaml`):**
```yaml
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

**Run:**
```bash
python cli.py train
```

---

### 2. Anthropic Teacher + Ollama Student

**Best for**: Users with Anthropic API access

**Setup:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
ollama serve
ollama pull qwen2.5-coder:32b
```

**Config:**
```yaml
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

**Run:**
```bash
python cli.py train
```

---

### 3. Together AI Teacher + Ollama Student

**Best for**: Cost-effective cloud optimization with local student

**Setup:**
```bash
export TOGETHER_API_KEY=...
ollama serve
ollama pull qwen2.5-coder:32b
```

**Config:**
```yaml
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

**Run:**
```bash
python cli.py train --config config/openai-compatible-example.yaml
```

---

### 4. OpenRouter Teacher + Ollama Student

**Best for**: Access to multiple models via single API

**Setup:**
```bash
export OPENROUTER_API_KEY=sk-or-...
ollama serve
ollama pull qwen2.5-coder:32b
```

**Config:**
```yaml
models:
  teacher:
    provider: "openai-compatible"
    model: "anthropic/claude-3.5-sonnet"  # or any OpenRouter model
    api_base: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"

  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

---

### 5. Local vLLM Teacher + Ollama Student

**Best for**: Fully local optimization (no API costs)

**Setup:**
```bash
# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3.1-70B-Instruct \
  --port 8000

# Start Ollama
ollama serve
ollama pull qwen2.5-coder:32b
```

**Config:**
```yaml
models:
  teacher:
    provider: "openai-compatible"
    model: "meta-llama/Meta-Llama-3.1-70B-Instruct"
    api_base: "http://localhost:8000/v1"
    api_key_env: null  # No API key needed for local

  student:
    provider: "ollama"
    model: "qwen2.5-coder:32b"
    api_base: "http://localhost:11434/v1"
```

---

### 6. OpenAI for Both (Testing)

**Best for**: Quick testing without local setup

**Setup:**
```bash
export OPENAI_API_KEY=sk-...
```

**Config:**
```yaml
models:
  teacher:
    provider: "openai"
    model: "gpt-4o"
    api_key_env: "OPENAI_API_KEY"

  student:
    provider: "openai"
    model: "gpt-4o-mini"  # Cheaper student
    api_key_env: "OPENAI_API_KEY"
```

**Run:**
```bash
python cli.py train --config config/openai-example.yaml
```

---

## Provider-Specific Notes

### OpenAI

- **Models**: `gpt-4o`, `gpt-4-turbo`, `gpt-4o-mini`
- **API Key**: Required (`OPENAI_API_KEY`)
- **API Base**: Leave as `null` (uses default)
- **Cost**: ~$0.005-0.03 per 1K tokens

### Anthropic

- **Models**: `claude-sonnet-4-5`, `claude-opus-4`, `claude-haiku-4`
- **API Key**: Required (`ANTHROPIC_API_KEY`)
- **API Base**: Leave as `null` (uses default)
- **Cost**: ~$0.003-0.015 per 1K tokens

### Together AI

- **Models**: See [Together AI docs](https://docs.together.ai/docs/inference-models)
- **API Key**: Required (`TOGETHER_API_KEY`)
- **API Base**: `https://api.together.xyz/v1`
- **Cost**: ~$0.0002-0.002 per 1K tokens (much cheaper!)
- **Popular models**:
  - `meta-llama/Meta-Llama-3.1-70B-Instruct`
  - `Qwen/Qwen2.5-72B-Instruct`
  - `mistralai/Mixtral-8x22B-Instruct-v0.1`

### OpenRouter

- **Models**: 100+ models from different providers
- **API Key**: Required (`OPENROUTER_API_KEY`)
- **API Base**: `https://openrouter.ai/api/v1`
- **Cost**: Varies by model ($0.0001-0.03 per 1K tokens)
- **Advantage**: Single API for all providers

### vLLM (Local)

- **Models**: Any HuggingFace model you can download
- **API Key**: Not needed (local)
- **API Base**: `http://localhost:8000/v1` (or custom port)
- **Cost**: Free (requires GPU)
- **Setup**: See [vLLM docs](https://docs.vllm.ai/)

### Ollama (Local)

- **Models**: See [Ollama library](https://ollama.com/library)
- **API Key**: Not needed (local)
- **API Base**: `http://localhost:11434/v1`
- **Cost**: Free (CPU or GPU)
- **Popular models**:
  - `qwen2.5-coder:32b` - Excellent for code
  - `deepseek-coder-v2:16b` - Fast, good quality
  - `codellama:34b` - Good general coding
  - `llama3.1:70b` - Strong reasoning

## Choosing Models

### Teacher Model Selection

**Requirements:**
- Strong reasoning ability
- Good instruction following
- Can generate diverse candidate prompts

**Recommendations:**
- **Best**: GPT-4o, Claude Sonnet 4.5
- **Good**: Llama 3.1 70B, Qwen 2.5 72B (via Together AI)
- **Budget**: GPT-4o-mini, Claude Haiku

### Student Model Selection

**Requirements:**
- The model you actually want to use in production
- Usually smaller/cheaper than teacher
- Can run locally if desired

**Recommendations:**
- **Local 32B+**: qwen2.5-coder:32b, codellama:34b
- **Local 16B**: deepseek-coder-v2:16b, qwen2.5-coder:14b
- **Cloud**: GPT-4o-mini, Claude Haiku (for testing)

## Troubleshooting

### "Failed to configure LM" Error

**Check:**
1. Provider name is correct (`openai`, `anthropic`, `openai-compatible`, `ollama`)
2. API key environment variable is set
3. API base URL is correct (for openai-compatible/ollama)
4. Model name matches provider's model naming

### "Connection refused" Error (Ollama/vLLM)

**Fix:**
```bash
# For Ollama
ollama serve

# For vLLM
python -m vllm.entrypoints.openai.api_server --model <model_name>
```

### "Invalid API key" Error

**Fix:**
```bash
# Check the environment variable name matches your config
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $TOGETHER_API_KEY

# Set if not set
export OPENAI_API_KEY=your_key_here
```

### Rate Limiting

**For OpenAI/Anthropic:**
- Reduce `num_threads` in config
- Use fewer training examples
- Add delays between requests

**For OpenAI-compatible:**
- Check provider's rate limits
- Some providers (Together AI) have higher limits

## Validation

Always validate your configuration before running optimization:

```bash
python cli.py validate
```

This will show:
- Provider configuration
- Model names
- API base URLs
- API key status

Example output:
```
Teacher Model Configuration:
  Provider: openai
  Model: gpt-4o
  API Base: None
  API Key: ✓ Set (OPENAI_API_KEY)

Student Model Configuration:
  Provider: ollama
  Model: qwen2.5-coder:32b
  API Base: http://localhost:11434/v1
  API Key: Not required
```

## Cost Estimation

For a typical optimization run with 20 training examples:

| Teacher Model | Approx Cost |
|---------------|-------------|
| GPT-4o | $0.50-2.00 |
| GPT-4-turbo | $1.00-3.00 |
| Claude Sonnet 4.5 | $0.30-1.50 |
| Llama 3.1 70B (Together AI) | $0.05-0.20 |
| Local vLLM | Free |

Student model costs are typically negligible if using local Ollama.

## Best Practices

1. **Start with OpenAI/Anthropic** - Easiest to set up, best quality
2. **Move to Together AI** - Once you understand the system, save costs
3. **Use local models** - For student when possible (no inference costs)
4. **Test with small datasets first** - Validate config with 5-10 examples
5. **Monitor costs** - Check provider dashboards during optimization

## Support

For provider-specific issues:
- **OpenAI**: https://platform.openai.com/docs
- **Anthropic**: https://docs.anthropic.com
- **Together AI**: https://docs.together.ai
- **OpenRouter**: https://openrouter.ai/docs
- **Ollama**: https://ollama.com
- **vLLM**: https://docs.vllm.ai
