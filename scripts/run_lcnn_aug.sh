#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
.venv/Scripts/python -u -m cm.run_baselines --models lcnn8_aug > artifacts/logs/run_lcnn8_aug.log 2>&1
echo "exit=$?" >> artifacts/logs/run_lcnn8_aug.log
