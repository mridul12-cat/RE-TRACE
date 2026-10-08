#!/usr/bin/env bash
# ==============================================================================
# scripts/start_demo.sh — RE:TRACE Interactive Hackathon Demo Launcher
# ==============================================================================
# IEEE Hackathon Sustainable Supply Chains Track Demo Runner
# Launches the FastAPI verification backend and interactive Web Dashboard.
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================================"
echo "  RE:TRACE — Verifiable Circular Economy & Climate Tracking Platform"
echo "  IEEE Sustainable Supply Chains Track"
echo "======================================================================"

# Check for virtual environment
if [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
    UVICORN_EXEC="$DIR/.venv/bin/uvicorn"
elif command -v python3 &> /dev/null; then
    PYTHON_EXEC="python3"
    UVICORN_EXEC="uvicorn"
else
    echo "[-] Error: Python 3 virtual environment or interpreter not found."
    exit 1
fi

export PYTHONPATH="$DIR/.venv/lib/python3.9/site-packages:$DIR"
export RETRACE_ENVIRONMENT="development"
export RETRACE_BLOCKCHAIN_NETWORK="LOCAL TESTNET (Chain ID: 31337)"

# Ensure storage directories exist
mkdir -p "$DIR/backend/data/uploads"
mkdir -p "$DIR/backend/data/certificates"

echo ""
echo "[+] Starting RE:TRACE Backend & Dashboard..."
echo "----------------------------------------------------------------------"
echo "  * Web Dashboard:      http://localhost:8000/dashboard"
echo "  * Alternative Root:   http://localhost:8000/"
echo "  * API Documentation:  http://localhost:8000/docs"
echo "  * Ledger Network:     LOCAL TESTNET (Chain ID 31337 - Anvil/Hardhat)"
echo "----------------------------------------------------------------------"
echo "[*] Evaluator Demo Scenarios Available in Dashboard:"
echo "    - Scenario A: Legitimate EV Battery Recycling -> PoR Issued (VERIFIED)"
echo "    - Scenario B: Impossible Material Recovery Claim -> Stoichiometric Gate Quarantined (FLAGGED)"
echo "    - Scenario C: Evidence Tampering Attack -> RFC 8785 Keccak-256 Mismatch (REJECTED)"
echo "----------------------------------------------------------------------"
echo "[*] Press Ctrl+C to terminate the demo server."
echo ""

exec "$UVICORN_EXEC" backend.app.main:app --host 0.0.0.0 --port 8000 --reload
