import os
import sys
import csv
import json
import requests
from datetime import datetime
from pathlib import Path


def check_health():
    """Verify OpenRouter API connection with a simple test request."""
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment variables")
        print("Please run setup.sh to configure your API key")
        return False

    print("Testing OpenRouter API connection...")

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/moralbench",
                "X-Title": "MoralBench",
            },
            json={
                "model": "openai/gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": "Say 'OK' if you can read this."
                    }
                ]
            },
            timeout=30
        )

        if response.status_code == 200:
            print("✓ OpenRouter API connection successful")
            return True
        else:
            print(f"✗ API request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False


def process_prompts():
    """Read prompts from CSV and get responses from OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = "openai/gpt-4o"

    # Read input CSV
    prompts_file = Path("prompts/v1.csv")
    if not prompts_file.exists():
        print(f"Error: {prompts_file} not found")
        return

    print(f"\nReading prompts from {prompts_file}...")

    with open(prompts_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prompts = list(reader)

    print(f"Found {len(prompts)} prompts to process")

    # Prepare output directory and file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path("results/v1")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name = model.replace("/", "_")
    output_file = output_dir / f"{model_name}_{timestamp}.csv"

    print(f"Output will be saved to: {output_file}")
    print("\nProcessing prompts...\n")

    results = []

    for i, prompt in enumerate(prompts, 1):
        topic = prompt.get('Topic', '')
        question = prompt.get('Question', '')

        print(f"[{i}/{len(prompts)}] Processing: {topic}")

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/moralbench",
                    "X-Title": "MoralBench",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": question
                        }
                    ]
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                model_response = data['choices'][0]['message']['content']
                print(f"  ✓ Got response ({len(model_response)} chars)")
            else:
                model_response = f"ERROR: Status {response.status_code} - {response.text}"
                print(f"  ✗ Request failed: {response.status_code}")

        except Exception as e:
            model_response = f"ERROR: {str(e)}"
            print(f"  ✗ Error: {e}")

        results.append({
            'Topic': topic,
            'Question': question,
            'Model Response': model_response,
            'Timestamp': datetime.now().isoformat()
        })

    # Write results to CSV
    print(f"\nWriting results to {output_file}...")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Topic', 'Question', 'Model Response', 'Timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"✓ Complete! Results saved to {output_file}")


def main():
    """Main entry point for MoralBench."""
    print("========================================")
    print("  MoralBench - LLM Morality Testing")
    print("========================================\n")

    # Run health check
    if not check_health():
        print("\nHealth check failed. Please verify your setup.")
        sys.exit(1)

    # Process prompts
    try:
        process_prompts()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during processing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
