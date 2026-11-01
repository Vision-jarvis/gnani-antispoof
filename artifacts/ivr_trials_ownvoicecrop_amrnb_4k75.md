# IVR flow on real audio, CM gate only (echo STT, identity gate bypassed)

Operating points are fixed on ASVspoof dev scores (`cm.calibrate`); nothing is tuned on these trials.

| source                       | operating_point   |   tau_llr |   n_bona |   n_spoof |   genuine_success_pct |   attack_success_pct |   short_audio |   median_latency_ms |
|:-----------------------------|:------------------|----------:|---------:|----------:|----------------------:|---------------------:|--------------:|--------------------:|
| wav:amrnb_4k75/bona vs spoof | far1              |     3.027 |       13 |        15 |                  15.4 |                 13.3 |             0 |               78.75 |
| wav:amrnb_4k75/bona vs spoof | min_dcf           |    -0.715 |       13 |        15 |                 100   |                 93.3 |             0 |               63.95 |
| wav:amrnb_4k75/bona vs spoof | eer               |     0.49  |       13 |        15 |                 100   |                 80   |             0 |               63.6  |
