#!/usr/bin/env bash
# One-time Modal setup for the two GPU jobs (run from the repo root in Git Bash, after the CPU data build).
# Uploads only the packed audio stores and manifests (about 4.2 GB), never data/raw, feature caches or .env.
set -euo pipefail
pip install modal
modal setup                                  # browser login, writes ~/.modal.toml (student account)
modal volume create gnani-cm-data || true    # ok if it already exists
for split in train dev eval; do
  for f in data/proc/asv19/$split/*.npz data/proc/asv19/$split/manifest.csv; do
    modal volume put --force gnani-cm-data "$f" "/asv19/$split/$(basename "$f")"
  done
done
for f in data/proc/indic_pilot/eval/*.npz data/proc/indic_pilot/eval/manifest.csv; do
  modal volume put --force gnani-cm-data "$f" "/indic_pilot/eval/$(basename "$f")"
done
modal volume ls gnani-cm-data /asv19/eval
echo "Next: modal run cm/modal_pretrained.py --limit 20   (dry run), then modal run cm/modal_pretrained.py"
