# Entry point on Windows (no make). Usage: .\run.ps1 <task>
#   setup     create .venv and install requirements (CPU torch)
#   quick     smoke test, under 5 minutes: unit tests (offline) + teacher smoke + mock IVR demo + report (from release/ on a fresh clone)
#   pipeline  full CPU pipeline (subset build, baselines, calibration, report); resumable, logs in artifacts/logs
#   report    rebuild artifacts/results.md from artifacts/scores (restores release/ first if needed)
#   trials    IVR flow on real ASVspoof clips at the dev-fixed operating points (uses the release pack without data/)
#   release   refresh release/ from artifacts/ and data/ (models, calibration, gzipped scores, audit, eval pack)
#   gpu-pretrained   Modal job 1: AASIST, AASIST-L, SSL+AASIST on all conditions + Indic pilot (about $1, cap $2.84)
#   gpu-teacher      Modal job 2: teacher fine-tune + scoring (about $4 to $6.50, cap $15.50)
#   onnx      export the 8 kHz LCNN to ONNX and measure RTF / RAM on one core
#   serve     FastAPI service on http://127.0.0.1:8000 (GNANI_MODE=mock by default)
#   demo      offline IVR demo on the mock Gnani backend
#   probe     5 real Gnani calls (spends credits) to re-verify API shapes
#   live-test pytest -m live (2 real Gnani calls)
param([Parameter(Mandatory = $true)][string]$Task)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$py = ".\.venv\Scripts\python.exe"
switch ($Task) {
    "setup" {
        python -m venv .venv
        & $py -m pip install --upgrade pip
        & $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
        & $py -m pip install -r requirements.txt
        if (-not (Test-Path third_party\aasist)) { git clone --depth 1 https://github.com/clovaai/aasist third_party/aasist }
        if (-not (Test-Path third_party\SSL_Anti-spoofing)) { git clone --depth 1 https://github.com/TakHemlata/SSL_Anti-spoofing third_party/SSL_Anti-spoofing }
    }
    "quick" {
        & $py -m pytest
        & $py -m cm.teacher.train --smoke
        & $py -m cm.release restore
        & $py -m ivr_demo.demo
        & $py -m eval.report | Select-Object -First 40
    }
    "pipeline" { & "C:\Program Files\Git\bin\bash.exe" scripts/run_pipeline.sh }
    "report" { & $py -m cm.release restore; & $py -m eval.report }
    "trials" { if (Test-Path data/proc/asv19/eval/g711u.npz) { & $py -m ivr_demo.trials } else { & $py -m ivr_demo.trials --pack } }
    "release" { & $py -m cm.release build }
    "gpu-pretrained" { modal run cm/modal_pretrained.py; & $py -m eval.report; & $py -m eval.indic_report }
    "gpu-teacher" { modal run cm/teacher/modal_train.py; & $py -m eval.report }
    "onnx" { & $py -m cm.export_onnx }
    "serve" { & $py -m uvicorn service.app:app --port 8000 }
    "demo" { & $py -m cm.release restore; & $py -m ivr_demo.demo }
    "probe" { & $py scripts/gnani_live_probe.py --yes }
    "live-test" { & $py -m pytest -m live }
    default { Write-Error "unknown task $Task" }
}
