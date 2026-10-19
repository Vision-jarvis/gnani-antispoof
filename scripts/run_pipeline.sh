#!/usr/bin/env bash
# Full CPU pipeline: build the ASVspoof subsets, train/score every baseline, calibrate, report.
# Resumable: each step is skipped when its output already exists. Logs go to artifacts/logs/.
set -u
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
PY=.venv/Scripts/python
L=artifacts/logs
mkdir -p $L
step() { echo "$(date '+%F %T') $*" >> $L/pipeline.log; }

[ -f data/proc/asv19/train/manifest.csv ] || { step build train; $PY -m factory.asvspoof --split train --n-bona 2580 --n-spoof-per-attack 430 > $L/build_train.log 2>&1; }
[ -f data/proc/asv19/dev/manifest.csv ] || { step build dev; $PY -m factory.asvspoof --split dev --n-bona 1000 --n-spoof-per-attack 170 > $L/build_dev.log 2>&1; }
[ -f data/proc/asv19/eval/manifest.csv ] || { step build eval; $PY -m factory.asvspoof --split eval --n-bona 1000 --n-spoof-per-attack 120 > $L/build_eval.log 2>&1 || { step FAIL build eval; exit 1; }; }
for m in gmm8_aug gmm16_clean aasist_l lcnn8_noaug lcnn8_aug aasist; do
  [ -f artifacts/scores/$m.csv ] && continue
  step run $m
  $PY -m cm.run_baselines --models $m > $L/run_$m.log 2>&1 || step FAIL $m
done
$PY -m cm.calibrate --model lcnn8_aug >> $L/pipeline.log 2>&1
$PY -m eval.report > $L/report.log 2>&1 || step FAIL report
step PIPELINE_DONE
