# IVR flow on real audio, CM gate only (echo STT, identity gate bypassed)

Operating points are fixed on ASVspoof dev scores (`cm.calibrate`); nothing is tuned on these trials.

| source                               | operating_point   |   tau_llr |   n_bona |   n_spoof |   genuine_success_pct |   attack_success_pct |   short_audio |   median_latency_ms |
|:-------------------------------------|:------------------|----------:|---------:|----------:|----------------------:|---------------------:|--------------:|--------------------:|
| ASVspoof19 eval g711u (release pack) | far1              |     3.027 |       60 |        60 |                  31.7 |                  5   |             7 |                50.1 |
| ASVspoof19 eval g711u (release pack) | min_dcf           |    -0.715 |       60 |        60 |                  93.3 |                 63.3 |             7 |                35.5 |
| ASVspoof19 eval g711u (release pack) | eer               |     0.49  |       60 |        60 |                  86.7 |                 45   |             7 |                35.1 |
