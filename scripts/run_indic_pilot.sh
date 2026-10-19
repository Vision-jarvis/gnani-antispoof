#!/usr/bin/env bash
# Build the Indic pilot set and score every trained baseline on it (after run_pipeline.sh).
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
[ -f data/proc/indic_pilot/eval/manifest.csv ] || .venv/Scripts/python -m factory.indic_pilot --per-class-per-lang 300 > artifacts/logs/build_indic_pilot.log 2>&1
