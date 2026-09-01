#!/usr/bin/env bash
# ==============================================================================
# Image Gen Pipeline Studio - High-Precision Desktop Launcher
# ==============================================================================

set -e

# ANSI Color Codes
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
MAGENTA="\033[0;35m"
DIM="\033[2m"
RESET="\033[0m"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo -e "\n${BOLD}${MAGENTA}================================================================${RESET}"
echo -e "${BOLD}${CYAN}   🚀 FASHION AI STUDIO — LOCAL DEV LAUNCHER${RESET}"
echo -e "${DIM}   Fully Local Dev Mode | Local Storage (./storage) | Zero-Config${RESET}"
echo -e "${BOLD}${MAGENTA}================================================================${RESET}\n"

# Enforce local development environment variables
export ENVIRONMENT="local"
export STORAGE_DIR="./storage"
export DEBUG="True"

# Helper for step status
print_step() {
    local step_num="$1"
    local total_steps="6"
    local title="$2"
    echo -e "${BOLD}${CYAN}[${step_num}/${total_steps}]${RESET} ${BOLD}${title}${RESET}"
}

print_success() {
    echo -e "      ${GREEN}✓${RESET} $1"
}

print_warning() {
    echo -e "      ${YELLOW}⚠️  $1${RESET}"
}

print_error() {
    echo -e "      ${RED}✗ $1${RESET}"
}

print_info() {
    echo -e "      ${DIM}ℹ $1${RESET}"
}

# Function to reliably kill processes by PID and port
kill_stale_processes() {
    local target_port="$1"
    local pids
    pids=$(lsof -ti tcp:"$target_port" 2>/dev/null || true)

    if [ -n "$pids" ]; then
        print_warning "Port $target_port is currently in use by PID(s): $(echo $pids | tr '\n' ' ')"
        print_info "Terminating stale process(es)..."

        for pid in $pids; do
            pkill -P "$pid" 2>/dev/null || true
            kill -15 "$pid" 2>/dev/null || true
        done

        sleep 0.5

        # Force kill (-9) any stubborn processes still hanging on the port
        pids_remaining=$(lsof -ti tcp:"$target_port" 2>/dev/null || true)
        if [ -n "$pids_remaining" ]; then
            for pid in $pids_remaining; do
                kill -9 "$pid" 2>/dev/null || true
            done
            sleep 0.5
        fi

        if lsof -i tcp:"$target_port" &>/dev/null; then
            print_error "Unable to release port $target_port. Please close conflicting apps manually."
            exit 1
        else
            print_success "Port $target_port successfully freed and ready."
        fi
    else
        print_success "Port $target_port is available."
    fi
}

# Cleanup hook on termination (Ctrl+C, script exit, terminal window close)
CLEANUP_DONE=0
cleanup() {
    if [ "$CLEANUP_DONE" = "1" ]; then
        return
    fi
    CLEANUP_DONE=1

    echo -e "\n${YELLOW}🛑 Shutting down Studio server and cleaning up processes...${RESET}" 2>/dev/null || true

    # 1. Kill tracked server PID and all its child processes
    if [ -n "${SERVER_PID:-}" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        pkill -P "$SERVER_PID" 2>/dev/null || true
        kill -15 "$SERVER_PID" 2>/dev/null || true
        sleep 0.2
        kill -9 "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi

    # 2. Ensure any process listening on the studio port is also terminated
    if [ -n "${PORT:-}" ]; then
        local port_pids
        port_pids=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
        if [ -n "$port_pids" ]; then
            for p in $port_pids; do
                pkill -P "$p" 2>/dev/null || true
                kill -15 "$p" 2>/dev/null || true
            done
            sleep 0.2
            for p in $port_pids; do
                kill -9 "$p" 2>/dev/null || true
            done
        fi
    fi

    echo -e "${GREEN}✓ Studio server and all background processes stopped cleanly.${RESET}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM HUP QUIT

# ------------------------------------------------------------------------------
# STEP 1: Verify Workspace Directory
# ------------------------------------------------------------------------------
print_step "1" "Verifying Project Workspace"
print_info "Root directory: $DIR"
if [ ! -d "src/app" ] || [ ! -d "src/frontend" ]; then
    print_error "Cannot find 'src/app' or 'src/frontend' directory in $DIR."
    exit 1
fi
print_success "Workspace structure verified (FastAPI backend + React frontend)."

# ------------------------------------------------------------------------------
# STEP 2: Verify & Auto-Install uv (Fast Python Package & Environment Manager)
# ------------------------------------------------------------------------------
print_step "2" "Checking Package Manager (uv)"

# Check standard PATH locations first
for candidate_dir in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.bin" "/opt/homebrew/bin" "/usr/local/bin"; do
    if [ -d "$candidate_dir" ] && [[ ":$PATH:" != *":$candidate_dir:"* ]]; then
        export PATH="$candidate_dir:$PATH"
    fi
done

if ! command -v uv &> /dev/null; then
    print_warning "'uv' package manager not found. Installing automatically..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        for candidate_dir in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.bin"; do
            if [ -f "$candidate_dir/uv" ]; then
                export PATH="$candidate_dir:$PATH"
                break
            fi
        done
    else
        print_error "'curl' is not available. Cannot install uv."
        print_error "Please install curl or uv manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

if ! command -v uv &> /dev/null; then
    print_error "Failed to install uv. Please install it manually: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

UV_VER=$(uv --version 2>/dev/null || echo "uv")
print_success "'$UV_VER' detected and ready."

# ------------------------------------------------------------------------------
# STEP 3: Environment Synchronization & Locked Dependencies
# ------------------------------------------------------------------------------
print_step "3" "Synchronizing Python Virtual Environment & Locked Dependencies"

print_info "Syncing dependencies strictly from project configuration (pyproject.toml / uv.lock)..."
if [ -f "uv.lock" ]; then
    uv sync --frozen
else
    uv sync
fi
source .venv/bin/activate
PYTHON_EXEC="$(which python)"
PYTHON_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
print_success "Virtual environment synchronized with uv: Python v$PYTHON_VER"

# ------------------------------------------------------------------------------
# STEP 4: Configuration & API Key Setup
# ------------------------------------------------------------------------------
print_step "4" "Validating Environment Configuration (.env)"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_info "No .env found. Creating .env from .env.example template..."
        cp .env.example .env
        print_success ".env file created from .env.example"
    else
        print_info "No .env or .env.example found. Generating default .env..."
        cat <<EOF > .env
GEMINI_API_KEY=your_google_ai_studio_api_key_here
PORT=7860
HOST=127.0.0.1
DEBUG=True
ENVIRONMENT=local
STORAGE_DIR=./storage
GCP_PROJECT_ID=ai-art-director-prod
GCS_BUCKET=ai-art-director-prod-store
VISION_MODEL=gemini-3.5-flash-lite
IMAGEN_MODEL=gemini-3-pro-image
INPAINT_MODEL=gemini-3-pro-image
EOF
        print_success "Default .env generated"
    fi
fi

# Load variables safely
set -a
source .env 2>/dev/null || true
set +a

PORT="${PORT:-7860}"
HOST="${HOST:-127.0.0.1}"
GCP_PROJECT_ID="${GCP_PROJECT_ID:-ai-art-director-prod}"
GCS_BUCKET="${GCS_BUCKET:-ai-art-director-prod-store}"
ENVIRONMENT="${ENVIRONMENT:-local}"
VISION_MODEL="${VISION_MODEL:-gemini-3.5-flash-lite}"
IMAGEN_MODEL="${IMAGEN_MODEL:-gemini-3-pro-image}"
INPAINT_MODEL="${INPAINT_MODEL:-gemini-3-pro-image}"

# Strip inline comments or whitespace
VISION_MODEL=$(echo "$VISION_MODEL" | cut -d'#' -f1 | xargs)
IMAGEN_MODEL=$(echo "$IMAGEN_MODEL" | cut -d'#' -f1 | xargs)
INPAINT_MODEL=$(echo "$INPAINT_MODEL" | cut -d'#' -f1 | xargs)
GEMINI_KEY_CLEAN=$(echo "${GEMINI_API_KEY:-}" | cut -d'#' -f1 | xargs)

if [ -z "$GEMINI_KEY_CLEAN" ] || [ "$GEMINI_KEY_CLEAN" = "your_google_ai_studio_api_key_here" ] || [ "$GEMINI_KEY_CLEAN" = "YOUR_GEMINI_API_KEY_HERE" ]; then
    print_warning "GEMINI_API_KEY is not configured yet in .env."
    echo -e "      ${BOLD}${YELLOW}Get a Gemini API key at: ${CYAN}https://aistudio.google.com/app/apikey${RESET}"
    
    # Prompt interactively if stdin or /dev/tty is accessible
    user_key=""
    if [ -t 0 ]; then
        read -r -p "      🔑 Enter your Gemini API key (or press Enter to skip): " user_key
    elif [ -e /dev/tty ]; then
        read -r -p "      🔑 Enter your Gemini API key (or press Enter to skip): " user_key </dev/tty 2>/dev/null || true
    fi

    user_key=$(echo "$user_key" | xargs)
    if [ -n "$user_key" ]; then
        if grep -q "^GEMINI_API_KEY=" .env; then
            sed -i '' "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$user_key|" .env 2>/dev/null || sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$user_key|" .env
        else
            echo "GEMINI_API_KEY=$user_key" >> .env
        fi
        export GEMINI_API_KEY="$user_key"
        GEMINI_KEY_CLEAN="$user_key"
        KEY_PREVIEW="${GEMINI_KEY_CLEAN:0:6}...${GEMINI_KEY_CLEAN: -4}"
        print_success "GEMINI_API_KEY saved to .env (${KEY_PREVIEW})"
    else
        print_warning "No key entered. You can edit .env manually before performing generations."
    fi
fi

if [ -n "$GEMINI_KEY_CLEAN" ] && [ "$GEMINI_KEY_CLEAN" != "your_google_ai_studio_api_key_here" ] && [ "$GEMINI_KEY_CLEAN" != "YOUR_GEMINI_API_KEY_HERE" ]; then
    KEY_PREVIEW="${GEMINI_KEY_CLEAN:0:6}...${GEMINI_KEY_CLEAN: -4}"
    print_success "GEMINI_API_KEY configured (${KEY_PREVIEW})"
fi

# Firestore connection mode (Local Emulator vs Cloud Firestore)
if [ -n "${FIRESTORE_EMULATOR_HOST:-}" ]; then
    print_info "Firestore:      ${BOLD}Local Emulator (${FIRESTORE_EMULATOR_HOST})${RESET}"
elif lsof -i tcp:8181 &>/dev/null; then
    export FIRESTORE_EMULATOR_HOST="127.0.0.1:8181"
    print_info "Firestore:      ${BOLD}Local Emulator (127.0.0.1:8181)${RESET}"
else
    print_info "Firestore:      ${BOLD}Cloud Firestore (${GCP_PROJECT_ID})${RESET}"
fi

print_info "GCP Project:    ${BOLD}${GCP_PROJECT_ID}${RESET}"
print_info "GCS Bucket:     ${BOLD}${GCS_BUCKET}${RESET}"
print_info "Environment:    ${BOLD}${ENVIRONMENT}${RESET}"
print_info "Vision Model:   ${BOLD}${VISION_MODEL}${RESET}"
print_info "Imagen Model:   ${BOLD}${IMAGEN_MODEL}${RESET}"
print_info "Inpaint Model:  ${BOLD}${INPAINT_MODEL}${RESET}"

# ------------------------------------------------------------------------------
# STEP 5: Storage, Frontend Assets & Port Availability
# ------------------------------------------------------------------------------
print_step "5" "Checking Storage, Frontend Assets & Port Availability"

# Storage directories
mkdir -p "storage/moodboards" "storage/generations" "storage/logs" "storage/wardrobe/items" "storage/wardrobe/sources"
print_success "Storage directories verified (storage/moodboards, storage/generations, storage/logs, storage/wardrobe)."

# Frontend production assets — build fresh if npm available, otherwise use pre-committed dist/
if command -v npm &> /dev/null; then
    if [ ! -f "src/frontend/dist/index.html" ] || scripts/frontend_needs_build.sh; then
        print_info "Building frontend production assets with Vite..."
        (
            cd src/frontend
            if [ ! -d "node_modules" ]; then
                npm install --silent
            fi
            npm run build
        )
        print_success "Frontend assets freshly compiled into src/frontend/dist."
    else
        print_success "Frontend assets up to date (npm available, no source changes detected)."
    fi
else
    if [ -f "src/frontend/dist/index.html" ]; then
        print_success "Using pre-built frontend distribution (src/frontend/dist)."
    else
        print_error "No pre-built frontend found at src/frontend/dist/index.html and npm is not installed."
        print_error "Either install Node.js/npm to build the frontend, or ensure dist/ is committed to the repository."
        exit 1
    fi
fi

# Port availability & stale process cleanup
kill_stale_processes "$PORT"

# ------------------------------------------------------------------------------
# STEP 6: Launch Backend Server & Open Browser
# ------------------------------------------------------------------------------
print_step "6" "Starting Studio Server & Opening Browser"
print_info "Starting Uvicorn ASGI server on http://${HOST}:${PORT}..."

# Start uvicorn in background
python -m uvicorn --app-dir src app.main:app --host "$HOST" --port "$PORT" &
SERVER_PID=$!

# Poll /health endpoint with spinner
HEALTH_URL="http://${HOST}:${PORT}/health"
print_info "Waiting for Studio service to be ready..."

MAX_ATTEMPTS=30
ATTEMPT=0
SERVER_READY=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        SERVER_READY=true
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep 0.5
done

if [ "$SERVER_READY" = true ]; then
    echo -e "\n${BOLD}${GREEN}================================================================${RESET}"
    echo -e "${BOLD}${GREEN}   ✨ STUDIO IS READY & RUNNING!${RESET}"
    echo -e "${BOLD}   🌐 Studio Web App:       ${CYAN}http://localhost:${PORT}${RESET}"
    echo -e "${BOLD}   📚 Interactive API Docs: ${CYAN}http://localhost:${PORT}/docs${RESET}"
    echo -e "${BOLD}   📄 Log File:             ${CYAN}storage/logs/studio.log${RESET}"
    echo -e "${BOLD}   ⚡ Status:               ${GREEN}Healthy (200 OK)${RESET}"
    echo -e "${DIM}   (Press Ctrl+C in this terminal window to stop the server)${RESET}"
    echo -e "${BOLD}${GREEN}================================================================${RESET}\n"

    # Open in default browser
    if command -v open &> /dev/null; then
        print_info "Launching web browser to http://localhost:${PORT}..."
        open "http://localhost:${PORT}"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:${PORT}"
    fi
else
    print_error "Server did not respond to health check at $HEALTH_URL within timeout."
    print_warning "Please inspect backend logs above for any initialization errors."
fi

# Keep script running to show live server logs and maintain background process
wait "$SERVER_PID"
