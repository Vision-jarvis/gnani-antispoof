# IVR flow on real audio, CM gate only (echo STT, identity gate bypassed)

Operating points are fixed on ASVspoof dev scores (`cm.calibrate`); nothing is tuned on these trials.

| source                     | operating_point   |   tau_llr |   n_bona |   n_spoof |   genuine_success_pct |   attack_success_pct |   short_audio |   median_latency_ms |
|:---------------------------|:------------------|----------:|---------:|----------:|----------------------:|---------------------:|--------------:|--------------------:|
| ASVspoof19 eval g711u      | far1              |     3.027 |      200 |       200 |                  32.5 |                 11   |            29 |               30.5  |
| ASVspoof19 eval g711u      | min_dcf           |    -0.715 |      200 |       200 |                  88.5 |                 62.5 |            29 |               29.6  |
| ASVspoof19 eval g711u      | eer               |     0.49  |      200 |       200 |                  84.5 |                 49   |            29 |               28.7  |
| ASVspoof19 eval amrnb_4k75 | far1              |     3.027 |      200 |       200 |                   4.5 |                  1   |            33 |               29.95 |
| ASVspoof19 eval amrnb_4k75 | min_dcf           |    -0.715 |      200 |       200 |                  75.5 |                 55.5 |            33 |               29.15 |
| ASVspoof19 eval amrnb_4k75 | eer               |     0.49  |      200 |       200 |                  57.5 |                 33.5 |            33 |               31.1  |
