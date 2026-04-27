#!/bin/bash
# KEA Installation Script v3.0.0
#
# Usage:
#   bash install.sh                # Install for Claude Code (default)
#   bash install.sh --claude-code  # Install for Claude Code
#   bash install.sh --obsidian     # Install Obsidian CSS snippet only
#   bash install.sh --both         # Install for both Claude Code and Obsidian
#
# Claude Code installation target: ~/.claude/skills/kea/
# Obsidian installation target:    <vault>/.obsidian/snippets/

set -e

KEA_VERSION="4.0.0"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
MODE="claude-code"

for arg in "$@"; do
    case "$arg" in
        --claude-code) MODE="claude-code" ;;
        --obsidian)    MODE="obsidian" ;;
        --both)        MODE="both" ;;
        --help|-h)
            echo "Usage: bash install.sh [--claude-code|--obsidian|--both]"
            echo ""
            echo "  --claude-code  Install to ~/.claude/skills/kea/ (default)"
            echo "  --obsidian     Install CSS snippet to .obsidian/snippets/"
            echo "  --both         Install to both locations"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Run 'bash install.sh --help' for usage."
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
KEA_TOOLS_DIR="${PROJECT_ROOT}/kea"

ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
err()  { echo "  ✗ $*" >&2; }
step() { echo ""; echo "$*"; }

echo "========================================"
echo "  KEA Installer v${KEA_VERSION}"
echo "========================================"

# ---------------------------------------------------------------------------
# [1] Check Python (needed to verify tool layer)
# ---------------------------------------------------------------------------
step "[1/4] Checking Python..."
PYTHON_CMD=""

for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        # Use Python itself for version comparison — reliable regardless of shell
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
            PYTHON_CMD="$candidate"
            break
        fi
    fi
done

if [ -z "${PYTHON_CMD}" ]; then
    err "Python 3.11+ not found."
    err "Install Python: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1)
ok "${PYTHON_CMD} — ${PYTHON_VERSION}"

# ---------------------------------------------------------------------------
# [2] Check Git
# ---------------------------------------------------------------------------
step "[2/4] Checking Git..."
if command -v git &>/dev/null; then
    ok "Git found ($(git --version))"
else
    warn "Git not found. KEA uses git for version control."
    warn "KEA will work without it, but version control won't be available."
fi

# ---------------------------------------------------------------------------
# [3] Verify KEA Python tool layer
# ---------------------------------------------------------------------------
step "[3/4] Verifying KEA Python tool layer..."

if [ ! -d "${KEA_TOOLS_DIR}" ]; then
    err "kea/ not found at ${KEA_TOOLS_DIR}"
    err "Expected structure:"
    err "  ${PROJECT_ROOT}/"
    err "  ├── AgentFile/    (this directory)"
    err "  └── kea/          (Python tool layer)"
    exit 1
fi

if ! (cd "${PROJECT_ROOT}" && ${PYTHON_CMD} -m kea --help >/dev/null 2>&1); then
    err "KEA CLI failed. Try manually:"
    err "  cd ${PROJECT_ROOT} && ${PYTHON_CMD} -m kea --help"
    exit 1
fi

ok "KEA CLI verified"

# Run unit tests if tests/ directory exists and has test files
TESTS_DIR="${PROJECT_ROOT}/tests"
if [ -d "${TESTS_DIR}" ] && [ -n "$(find "${TESTS_DIR}" -name 'test_*.py' 2>/dev/null)" ]; then
    if (cd "${PROJECT_ROOT}" && ${PYTHON_CMD} -m pytest tests/ -q >/tmp/kea-test.log 2>&1); then
        TEST_COUNT=$(grep -oE '[0-9]+ passed' /tmp/kea-test.log | awk '{print $1}' | head -1)
        ok "All ${TEST_COUNT} tests passed"
    else
        warn "Some tests failed. Check /tmp/kea-test.log"
        tail -5 /tmp/kea-test.log >&2
    fi
else
    ok "No unit tests found — skipping"
fi

# Run AgentFile lint
if (cd "${PROJECT_ROOT}" && ${PYTHON_CMD} -m kea lint "${SCRIPT_DIR}" >/tmp/kea-lint.log 2>&1); then
    ok "AgentFile lint: 0 errors"
else
    warn "AgentFile lint found issues. Check /tmp/kea-lint.log"
    tail -5 /tmp/kea-lint.log >&2
fi

# ---------------------------------------------------------------------------
# [4] Obsidian Vault 路径配置
# ---------------------------------------------------------------------------
step "[4/5] Configuring Obsidian Vault path..."

CLAUDE_SKILLS_DIR="${HOME}/.claude/skills/kea"
CONFIG_FILE="${CLAUDE_SKILLS_DIR}/config.md"

# Check if already configured
EXISTING_VAULT=""
if [ -f "${CONFIG_FILE}" ]; then
    EXISTING_VAULT=$(grep "^VAULT_PATH:" "${CONFIG_FILE}" | awk '{print $2}')
fi

# Non-interactive mode: use KEA_VAULT_PATH env var if set
if [ -n "${KEA_VAULT_PATH}" ]; then
    VAULT_PATH="${KEA_VAULT_PATH}"
    ok "Using KEA_VAULT_PATH env var: ${VAULT_PATH}"
elif [ -n "${EXISTING_VAULT}" ]; then
    echo "  Current vault: ${EXISTING_VAULT}"
    printf "  Enter new vault path (press Enter to keep current): "
    read -r INPUT_VAULT
    VAULT_PATH="${INPUT_VAULT:-${EXISTING_VAULT}}"
else
    printf "  Enter Obsidian Vault absolute path: "
    read -r VAULT_PATH
fi

if [ -z "${VAULT_PATH}" ]; then
    err "Vault path cannot be empty."
    err "Hint: set KEA_VAULT_PATH env var for non-interactive install."
    exit 1
fi

# Expand ~ to $HOME
VAULT_PATH="${VAULT_PATH/#\~/$HOME}"

if [ ! -d "${VAULT_PATH}" ]; then
    warn "Directory does not exist: ${VAULT_PATH}"
    warn "Please create it first, or verify the path."
    warn "Continuing with this path — agents will create subdirectories when needed."
fi

ok "Vault path: ${VAULT_PATH}"

# Pre-create vault subdirectories
mkdir -p \
    "${VAULT_PATH}/30-Ontology/objects/_shared" \
    "${VAULT_PATH}/30-Ontology/logic/_shared" \
    "${VAULT_PATH}/30-Ontology/actions/_shared" \
    "${VAULT_PATH}/30-Ontology/rules/_shared" \
    "${VAULT_PATH}/30-Ontology/diagrams" \
    "${VAULT_PATH}/30-Ontology/data-mock" \
    "${VAULT_PATH}/RAWData/KEAOutput/research" \
    "${VAULT_PATH}/RAWData/KEAOutput/interviews" \
    "${VAULT_PATH}/RAWData/KEAOutput/reports/coverage" \
    "${VAULT_PATH}/RAWData/KEAOutput/reports/validation"
ok "Vault directories initialized"

# ---------------------------------------------------------------------------
# [5] Install
# ---------------------------------------------------------------------------
step "[5/5] Installing..."

# --- Claude Code ---
install_claude_code() {
    CLAUDE_SKILLS_DIR="${HOME}/.claude/skills/kea"
    echo "  → Claude Code: ${CLAUDE_SKILLS_DIR}"

    mkdir -p "${CLAUDE_SKILLS_DIR}"

    # Write config.md with vault path and tools root
    cat > "${CLAUDE_SKILLS_DIR}/config.md" <<EOF
# KEA Config
VAULT_PATH: ${VAULT_PATH}
KEA_TOOLS_ROOT: ${PROJECT_ROOT}
EOF
    ok "config.md written (VAULT_PATH=${VAULT_PATH}, KEA_TOOLS_ROOT=${PROJECT_ROOT})"

    # Copy SKILL.md
    cp "${SCRIPT_DIR}/SKILL.md" "${CLAUDE_SKILLS_DIR}/SKILL.md"
    ok "SKILL.md installed"

    # Copy skills/ (sub-skills, each in own directory with SKILL.md)
    if [ -d "${SCRIPT_DIR}/skills" ]; then
        mkdir -p "${CLAUDE_SKILLS_DIR}/skills"
        cp -r "${SCRIPT_DIR}/skills/"* "${CLAUDE_SKILLS_DIR}/skills/"
        SKILL_COUNT=$(find "${SCRIPT_DIR}/skills" -name "SKILL.md" | wc -l | tr -d ' ')
        ok "${SKILL_COUNT} sub-skill files installed"
    fi

    # Copy templates/
    if [ -d "${SCRIPT_DIR}/templates" ]; then
        mkdir -p "${CLAUDE_SKILLS_DIR}/templates"
        cp "${SCRIPT_DIR}/templates/"*.md "${CLAUDE_SKILLS_DIR}/templates/"
        ok "Templates installed"
    fi

    # Copy docs/
    if [ -d "${SCRIPT_DIR}/docs" ]; then
        mkdir -p "${CLAUDE_SKILLS_DIR}/docs"
        cp "${SCRIPT_DIR}/docs/"*.md "${CLAUDE_SKILLS_DIR}/docs/"
        ok "Docs installed"
    fi

    # Copy phases/
    if [ -d "${SCRIPT_DIR}/phases" ]; then
        mkdir -p "${CLAUDE_SKILLS_DIR}/phases"
        cp "${SCRIPT_DIR}/phases/"*.md "${CLAUDE_SKILLS_DIR}/phases/"
        PHASE_COUNT=$(ls "${SCRIPT_DIR}/phases/"*.md 2>/dev/null | wc -l | tr -d ' ')
        ok "${PHASE_COUNT} phase files installed"
    fi

    # Verify
    if [ -f "${CLAUDE_SKILLS_DIR}/SKILL.md" ]; then
        ok "Verified: ${CLAUDE_SKILLS_DIR}/SKILL.md exists"
    else
        err "Verification failed: SKILL.md not found after install"
        exit 1
    fi
}

# --- Obsidian ---
install_obsidian() {
    OBSIDIAN_DIR="${PROJECT_ROOT}/.obsidian"

    if [ ! -d "${OBSIDIAN_DIR}" ]; then
        warn ".obsidian/ not found at ${PROJECT_ROOT}"
        warn "Run this script from inside your Obsidian vault."
        warn "Skipping Obsidian installation."
        return 0
    fi

    SNIPPETS_DIR="${OBSIDIAN_DIR}/snippets"
    mkdir -p "${SNIPPETS_DIR}"

    CSS_SRC="${SCRIPT_DIR}/assets/kea-graph-colors.css"
    CSS_DST="${SNIPPETS_DIR}/kea-graph-colors.css"

    if [ -f "${CSS_SRC}" ]; then
        cp "${CSS_SRC}" "${CSS_DST}"
        ok "CSS snippet installed: ${CSS_DST}"
    else
        err "CSS source not found: ${CSS_SRC}"
        err "Expected: AgentFile/assets/kea-graph-colors.css"
        exit 1
    fi

    echo ""
    echo "  Next steps in Obsidian:"
    echo "    1. Settings → Appearance → CSS snippets → Enable 'kea-graph-colors'"
    echo "    2. Settings → Community Plugins → Install 'obsidian-mermaid-links'"
    echo "    3. Open Graph View → Groups, add:"
    echo "         tag:#kea-domain → Purple"
    echo "         tag:#kea-object → Red"
    echo "         tag:#kea-logic  → Blue"
    echo "         tag:#kea-action → Green"
}

case "${MODE}" in
    claude-code) install_claude_code ;;
    obsidian)    install_obsidian ;;
    both)        install_claude_code; install_obsidian ;;
esac

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""

if [ "${MODE}" = "claude-code" ] || [ "${MODE}" = "both" ]; then
    echo "Claude Code — trigger KEA with any of:"
    echo "  'kea'  'KEA'  'ontology'  '知识萃取'  '本体建模'"
    echo ""
    echo "  KEA 默认启动本体萃取技能链（12 阶段 + 门控）"
    echo "  状态持久化于：{VAULT_PATH}/RAWData/KEAOutput/{domain}-chain-state.md"
    echo ""
    echo "  Vault: ${VAULT_PATH}"
    echo "  ├── 30-Ontology/"
    echo "  │   ├── objects/{domain}/   logic/{domain}/"
    echo "  │   ├── actions/{domain}/   rules/{domain}/"
    echo "  │   ├── diagrams/{domain}/"
    echo "  │   └── _shared/  (跨域共用)"
    echo "  └── RAWData/KEAOutput/    (chain-state / research / interviews / reports)"
    echo ""
    echo "  技能链完成后可用："
    echo "    /ontology-codegen    /ontology-index"
    echo "    /ontology-impact     /ontology-flowchart"
    echo ""
fi

if [ "${MODE}" = "obsidian" ] || [ "${MODE}" = "both" ]; then
    echo "Obsidian CSS snippet installed."
    echo ""
fi

echo "Python tool layer:"
echo "  cd ${PROJECT_ROOT}"
echo "  ${PYTHON_CMD} -m kea --help"
echo ""
