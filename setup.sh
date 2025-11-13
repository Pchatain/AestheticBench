#!/bin/bash

set -e

echo "=========================================="
echo "  MoralBench OpenRouter Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    echo "Found existing .env file."
    read -p "Do you want to update your OpenRouter API key? (y/n): " update_key
    if [[ ! "$update_key" =~ ^[Yy]$ ]]; then
        echo "Keeping existing API key."
        SKIP_KEY_INPUT=true
    fi
fi

# Get API key from user
if [ "$SKIP_KEY_INPUT" != "true" ]; then
    echo ""
    echo "Please get your OpenRouter API key from:"
    echo "https://openrouter.ai/keys"
    echo ""
    read -p "Paste your OpenRouter API key: " api_key

    if [ -z "$api_key" ]; then
        echo "Error: API key cannot be empty"
        exit 1
    fi

    # Create or update .env file
    if [ -f ".env" ]; then
        # Remove existing OPENROUTER_API_KEY line if present
        grep -v "^OPENROUTER_API_KEY=" .env > .env.tmp || true
        mv .env.tmp .env
    fi

    echo "OPENROUTER_API_KEY=$api_key" >> .env
    echo " API key saved to .env file"
fi

echo ""
echo "Checking for uv installation..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo ""
    echo "uv is not installed. uv is required to run this project."
    echo ""
    echo "To install uv, run:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://docs.astral.sh/uv/getting-started/installation/"
    echo ""
    read -p "Would you like to open the installation page? (y/n): " open_page
    if [[ "$open_page" =~ ^[Yy]$ ]]; then
        if command -v open &> /dev/null; then
            open "https://docs.astral.sh/uv/getting-started/installation/"
        elif command -v xdg-open &> /dev/null; then
            xdg-open "https://docs.astral.sh/uv/getting-started/installation/"
        fi
    fi
    echo ""
    echo "Please install uv and run this setup script again."
    exit 1
fi

echo " uv is installed"
echo ""
echo "Installing dependencies..."
uv sync

echo ""
echo "Running health check..."
echo ""

# Run health check
if uv run --env-file .env main.py; then
    echo ""
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "To run MoralBench in the future, use:"
    echo "  uv run --env-file .env main.py"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "  Health check failed"
    echo "=========================================="
    echo ""
    echo "Please check your API key and try again."
    exit 1
fi
