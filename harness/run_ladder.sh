#!/usr/bin/env bash
# Full ladder for one model and one track, most valuable first: levels 2-3 public, level-3 private, then level 1.
# Resumable: records already in the results files are skipped, so rerun after a rate-limit stop.
#   bash harness/run_ladder.sh claude-opus-5-5 agentic
set -u
model=$1; track=$2; trials=${3:-3}
cd "$(dirname "$0")/.."
ids() { ls tasks | grep -E "^($1)_[0-9]+\.json$" | sed 's/\.json$//' | tr '\n' ' '; }
run() { python -u harness/run_eval.py --transport claude-cli --model "$model" --track "$track" --trials "$trials" "$@"; }
run --tasks $(ids "bess|bess3")
run --private
run --tasks $(ids "mech|elec|comb|pe_cooling|coolant_loop")
