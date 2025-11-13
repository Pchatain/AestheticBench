# Introduction

This is a project to measure the morality of LLMs.

## Getting Started

First, git clone this repo and then open a terminal session and navigate to this folder.

Run setup.sh by copy and pasting the following command in your terminal:

```bash
./setup.sh
```

This will:
1. Prompt you for your OpenRouter API key (get one at https://openrouter.ai/keys)
2. Save the key to your `.env` file
3. Check for `uv` installation
4. Install dependencies
5. Run a health check

## Running Model Inference

After setup is complete, run model inference with:

```bash
uv run --env-file .env python main.py
```

This will:
- Verify the model exists on OpenRouter
- Process all prompts from `prompts/v1.csv`
- Send requests to OpenRouter API in parallel (default: 10 concurrent requests)
- Save results to `results/v1/<model-name>_<timestamp>.csv`

### CLI Options

You can customize the model and paths using command-line options:

```bash
# Use a different model
uv run --env-file .env python main.py --model anthropic/claude-3.5-sonnet

# Specify custom input/output paths
uv run --env-file .env python main.py -p prompts/custom.csv -o results/custom

# See all available options
uv run --env-file .env python main.py --help
```

### Configuration

You can customize the number of concurrent workers by setting the `MORALBENCH_WORKERS` environment variable:

```bash
# Use 5 concurrent workers
MORALBENCH_WORKERS=5 uv run --env-file .env python main.py

# Run sequentially (no parallelism)
MORALBENCH_WORKERS=0 uv run --env-file .env python main.py
```