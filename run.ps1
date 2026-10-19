# Entry point on Windows (no make). Usage: .\run.ps1 <task>
#   setup     create .venv and install requirements (CPU torch)
#   quick     smoke test, under 5 minutes: unit tests (offline) + mock IVR demo + report from existing scores
#   pipeline  full CPU pipeline (subset build, baselines, calibration, report); resumable, logs in artifacts/logs
#   report    rebuild artifacts/results.md from artifacts/scores
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
        & $py -m ivr_demo.demo
        if (Test-Path artifacts\scores) { & $py -m eval.report | Select-Object -First 40 }
    }
    "pipeline" { & "C:\Program Files\Git\bin\bash.exe" scripts/run_pipeline.sh }
    "report" { & $py -m eval.report }
    "onnx" { & $py -m cm.export_onnx }
    "serve" { & $py -m uvicorn service.app:app --port 8000 }
    "demo" { & $py -m ivr_demo.demo }
    "probe" { & $py scripts/gnani_live_probe.py --yes }
    "live-test" { & $py -m pytest -m live }
    default { Write-Error "unknown task $Task" }
}
