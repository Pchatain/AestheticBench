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

### First Time: Dry Run (Recommended)

Before running actual inference, it's recommended to do a dry run to:
- Verify all models are available
- See how many prompts will be processed
- Get cost estimates for API usage

```bash
uv run --env-file .env python main.py --dry-run
```

For multiple models:
```bash
uv run --env-file .env python main.py --models-file configurations/selected_models.txt --dry-run
```

### Running Inference

After verifying with a dry run, run model inference with:

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

# Run multiple models from a text file
uv run --env-file .env python main.py --models-file configurations/selected_models.txt

# Specify custom input/output paths
uv run --env-file .env python main.py -p prompts/custom.csv -o results/custom

# See all available options
uv run --env-file .env python main.py --help
```

#### Running Multiple Models

To test multiple models in sequence, create a text file with one model ID per line:

```text
# configurations/selected_models.txt
openai/gpt-4o
anthropic/claude-3.5-sonnet
google/gemini-pro-1.5
```

Then run:
```bash
uv run --env-file .env python main.py --models-file configurations/selected_models.txt
```

This will:
- Verify each model exists on OpenRouter
- Process all prompts for each model sequentially
- Save separate results files for each model
- Display a summary of successful and failed runs

### Configuration

You can customize the number of concurrent workers by setting the `MORALBENCH_WORKERS` environment variable:

```bash
# Use 5 concurrent workers
MORALBENCH_WORKERS=5 uv run --env-file .env python main.py

# Run sequentially (no parallelism)
MORALBENCH_WORKERS=0 uv run --env-file .env python main.py
```

## Grading Responses

After running inference, you can grade the model responses using an LLM-as-judge approach.

### Available Graders

- **preference1** - Categorical preference scoring (-1, 0, 1)
- **preference2** - Continuous preference scoring [-1, 1]
- **justification** - Quality rating (1-5 scale)

### Running Grading

```bash
# Grade with a single grader
uv run --env-file .env python main.py grade results/v1/responses/openai_gpt-4o_timestamp.csv --graders preference1

# Grade with multiple graders
uv run --env-file .env python main.py grade results/v1/responses/openai_gpt-4o_timestamp.csv --graders preference1,preference2,justification

# Interactive grader selection (prompts you to choose)
uv run --env-file .env python main.py grade results/v1/responses/openai_gpt-4o_timestamp.csv

# Use a different model for grading
uv run --env-file .env python main.py grade results/v1/responses/openai_gpt-4o_timestamp.csv --grader-model anthropic/claude-sonnet-4.5
```

### Output

Grading results are saved to `results/<version>/grades/` with additional score columns appended to the original CSV data.

# Roadmap
- [ ] Create a visualization server to analyze results
- [x] Create an LLM as judge to classify and sort replies

## Infra TODOs
- [ ] Add ruff linting and formatting to the code
- [ ] Cleanup architecture
- [ ] Add testing framework
- [ ] Setup CI/CD to distribute this as a package