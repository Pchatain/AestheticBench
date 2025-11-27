#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

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
    echo " API key saved to .env file"
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

echo " uv is installed"

# Check if npm is installed (required for frontend)
echo ""
echo "Checking for npm installation..."

if ! command -v npm &> /dev/null; then
    echo ""
    echo "npm is not installed. npm is required for the frontend visualization UI."
    echo ""
    echo "To install npm, you can:"
    echo "  1. Install Node.js (includes npm): https://nodejs.org/"
    echo "  2. Use a version manager like nvm: https://github.com/nvm-sh/nvm"
    echo "  3. On macOS with Homebrew: brew install node"
    echo ""
    read -p "Would you like to open the Node.js installation page? (y/n): " open_page
    if [[ "$open_page" =~ ^[Yy]$ ]]; then
        if command -v open &> /dev/null; then
            open "https://nodejs.org/"
        elif command -v xdg-open &> /dev/null; then
            xdg-open "https://nodejs.org/"
        fi
    fi
    echo ""
    echo "Please install npm and run this setup script again."
    exit 1
fi

echo " npm is installed ($(npm --version))"

echo ""
echo "Installing Python dependencies..."
uv sync

echo ""
echo "Installing frontend dependencies..."
cd "$PROJECT_DIR/packages/frontend"
npm install
cd "$PROJECT_DIR"

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

# Ask user if they want to start the visualization UI
echo ""
read -p "Would you like to start the visualization UI now? (y/n): " start_ui
if [[ "$start_ui" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting visualization servers..."
    echo ""
    
    # Detect OS and open terminals accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - use osascript to open new Terminal tabs
        osascript <<EOF
tell application "Terminal"
    activate
    do script "cd \"$PROJECT_DIR/packages/backend\" && echo 'Starting Backend Server...' && ./run.sh"
    delay 1
    tell application "System Events" to keystroke "t" using {command down}
    delay 0.5
    do script "cd \"$PROJECT_DIR/packages/frontend\" && echo 'Starting Frontend Server...' && npm run dev" in front window
end tell
EOF
        echo "Backend server starting at: http://localhost:8000"
        echo "Frontend server starting at: http://localhost:5173"
        echo ""
        echo "Two new terminal tabs have been opened:"
        echo "  - Tab 1: Backend API server (FastAPI)"
        echo "  - Tab 2: Frontend dev server (Vite)"
        echo ""
        echo "Open http://localhost:5173 in your browser to view the UI."
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - try gnome-terminal or xterm
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal --tab --title="Backend" -- bash -c "cd '$PROJECT_DIR/packages/backend' && echo 'Starting Backend Server...' && ./run.sh; exec bash"
            gnome-terminal --tab --title="Frontend" -- bash -c "cd '$PROJECT_DIR/packages/frontend' && echo 'Starting Frontend Server...' && npm run dev; exec bash"
        elif command -v xterm &> /dev/null; then
            xterm -title "Backend" -e "cd '$PROJECT_DIR/packages/backend' && ./run.sh" &
            xterm -title "Frontend" -e "cd '$PROJECT_DIR/packages/frontend' && npm run dev" &
        else
            echo "Could not detect a supported terminal emulator."
            echo "Please start the servers manually:"
            echo "  Backend: cd packages/backend && ./run.sh"
            echo "  Frontend: cd packages/frontend && npm run dev"
        fi
        echo ""
        echo "Backend server starting at: http://localhost:8000"
        echo "Frontend server starting at: http://localhost:5173"
    else
        echo "Automatic terminal opening not supported on this OS."
        echo "Please start the servers manually in separate terminals:"
        echo "  Backend: cd packages/backend && ./run.sh"
        echo "  Frontend: cd packages/frontend && npm run dev"
    fi
fi
