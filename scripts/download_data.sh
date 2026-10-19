#!/usr/bin/env bash
# Download every automatically obtainable dataset (resumable, stall-aware). See data/README.md.
cd "$(dirname "$0")/.."
R=data/raw
mkdir -p $R/asvspoof2019_la $R/asvspoof2021_la $R/indicsynth $R/fleurs/hi_in $R/fleurs/kn_in $R/in_the_wild
get() { for i in $(seq 1 40); do curl -sSL -C - --speed-limit 100000 --speed-time 60 -o "$2" "$1" && return 0; sleep 10; done; echo "FAIL $2"; return 1; }
H=https://huggingface.co/datasets
for s in train validation test; do get "$H/Bisher/ASVspoof_2019_LA/resolve/main/data/$s-00000-of-00001.parquet" $R/asvspoof2019_la/$s.parquet; done
get https://www.asvspoof.org/asvspoof2021/LA-keys-full.tar.gz $R/asvspoof2021_la/LA-keys-full.tar.gz
get "$H/vdivyasharma/IndicSynth/resolve/main/Hindi/train-00000-of-00107.parquet" $R/indicsynth/Hindi-00000.parquet
get "$H/vdivyasharma/IndicSynth/resolve/main/Kannada/train-00000-of-00091.parquet" $R/indicsynth/Kannada-00000.parquet
for L in hi_in kn_in; do for s in dev test; do
  get "$H/google/fleurs/resolve/main/data/$L/$s.tsv" $R/fleurs/$L/$s.tsv
  get "$H/google/fleurs/resolve/main/data/$L/audio/$s.tar.gz" $R/fleurs/$L/$s.tar.gz
done; done
get "https://zenodo.org/api/records/4837263/files/ASVspoof2021_LA_eval.tar.gz/content" $R/asvspoof2021_la/ASVspoof2021_LA_eval.tar.gz
get "$H/mueller91/In-The-Wild/resolve/main/release_in_the_wild.zip" $R/in_the_wild/release_in_the_wild.zip
