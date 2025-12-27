"""OpenRouter API client using httpx."""

import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import Optional

from .config import Config


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(self, config: Config):
        """Initialize the OpenRouter client.

        Args:
            config: Configuration object containing API credentials and settings.
        """
        self.config = config
        self._client = httpx.Client(
            headers=config.headers,
            timeout=config.request_timeout,
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close the client."""
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def get_available_models(self) -> Optional[list[dict]]:
        """Fetch list of available models from OpenRouter.

        Returns:
            List of model dictionaries if successful, None otherwise.
        """
        try:
            response = self._client.get(
                "https://openrouter.ai/api/v1/models",
                timeout=self.config.health_check_timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                print(f"✗ Failed to fetch models: {response.status_code}")
                return None

        except httpx.HTTPError as e:
            print(f"✗ Error fetching models: {e}")
            return None

    def get_model_info(self, model_name: str) -> Optional[dict]:
        """Get detailed information about a specific model.

        Args:
            model_name: The model ID to look up (e.g., "openai/gpt-4o").

        Returns:
            Dictionary with model information including pricing, or None if not found.
        """
        models = self.get_available_models()
        if models is None:
            return None

        for model in models:
            if model.get("id") == model_name:
                return model

        return None

    def verify_model(self, model_name: str, verbose: bool = True) -> bool:
        """Verify that a model exists in OpenRouter's available models.

        Args:
            model_name: The model ID to verify (e.g., "openai/gpt-4o").
            verbose: Whether to print verification messages.

        Returns:
            True if the model exists, False otherwise.
        """
        if verbose:
            print(f"Verifying model: {model_name}...")

        models = self.get_available_models()
        if models is None:
            if verbose:
                print("✗ Could not fetch available models")
            return False

        # Check if model exists
        model_ids = [model.get("id") for model in models]
        if model_name in model_ids:
            if verbose:
                print(f"✓ Model '{model_name}' is available")
            return True
        else:
            if verbose:
                print(f"✗ Model '{model_name}' not found")
                print(f"  Available models: {len(model_ids)} total")
                # Show similar models if any
                similar = [m for m in model_ids if model_name.split("/")[0] in m]
                if similar:
                    print(f"  Similar models: {', '.join(similar[:5])}")
            return False

    def health_check(self) -> bool:
        """Verify OpenRouter API connection with a simple test request.

        Returns:
            True if the connection is successful, False otherwise.
        """
        print("Testing OpenRouter API connection...")

        try:
            response = self._client.post(
                self.config.base_url,
                json={
                    "model": "openai/gpt-4o",
                    "messages": [
                        {"role": "user", "content": "Say 'OK' if you can read this."}
                    ],
                },
                timeout=self.config.health_check_timeout,
            )

            if response.status_code == 200:
                print("✓ OpenRouter API connection successful")
                return True
            else:
                print(f"✗ API request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except httpx.HTTPError as e:
            print(f"✗ Connection error: {e}")
            return False

    def chat_completion(
        self,
        message: str,
        model: str = "openai/gpt-4o",
        timeout: Optional[int] = None,
    ) -> str:
        """Send a single chat completion request.

        Args:
            message: The message to send to the model.
            model: The model to use for the completion.
            timeout: Optional timeout override for this request.

        Returns:
            The model's response text.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        response = self._client.post(
            self.config.base_url,
            json={"model": model, "messages": [{"role": "user", "content": message}]},
            timeout=timeout or self.config.request_timeout,
        )

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def batch_chat_completions(
        self,
        messages: list[str],
        model: str = "openai/gpt-4o",
        max_workers: Optional[int] = None,
    ) -> list[tuple[int, str, Optional[str]]]:
        """Send multiple chat completion requests in parallel using ThreadPoolExecutor.

        Args:
            messages: List of messages to send to the model.
            model: The model to use for completions.
            max_workers: Number of concurrent workers. If 0, run sequentially.
                        If None, use config.max_workers.

        Returns:
            List of tuples (index, message, response) where response is None if error occurred.
        """
        if max_workers is None:
            max_workers = self.config.max_workers

        results = []

        # Sequential mode when max_workers is 0
        if max_workers == 0:
            for i, message in tqdm(
                enumerate(messages),
                total=len(messages),
                desc="Processing prompts",
                unit="prompt",
                leave=True,
            ):
                try:
                    response = self.chat_completion(message, model)
                    results.append((i, message, response))
                except Exception as e:
                    tqdm.write(f"  ✗ Error: {e}")
                    results.append((i, message, None))
            return results

        # Parallel mode with ThreadPoolExecutor
        def process_message(index: int, message: str) -> tuple[int, str, Optional[str]]:
            """Process a single message and return result with index."""
            try:
                response = self.chat_completion(message, model)
                return (index, message, response)
            except Exception as e:
                tqdm.write(f"  ✗ Error processing message {index}: {e}")
                return (index, message, None)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(process_message, i, msg): i
                for i, msg in enumerate(messages)
            }

            # Collect results as they complete with progress bar
            with tqdm(
                total=len(messages),
                desc="Processing prompts",
                unit="prompt",
                leave=True,
            ) as pbar:
                for future in as_completed(future_to_index):
                    result = future.result()
                    results.append(result)
                    pbar.update(1)

        # Sort results by original index to maintain order
        results.sort(key=lambda x: x[0])
        return results
