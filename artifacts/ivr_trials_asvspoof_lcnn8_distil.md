# IVR flow on real audio, CM gate only (echo STT, identity gate bypassed)

Operating points are fixed on ASVspoof dev scores (`cm.calibrate`); nothing is tuned on these trials.

| source                     | operating_point   |   tau_llr |   n_bona |   n_spoof |   genuine_success_pct |   attack_success_pct |   short_audio |   median_latency_ms | model        |
|:---------------------------|:------------------|----------:|---------:|----------:|----------------------:|---------------------:|--------------:|--------------------:|:-------------|
| ASVspoof19 eval g711u      | far1              |     3.365 |      200 |       200 |                  35.5 |                  9   |            29 |                38.4 | lcnn8_distil |
| ASVspoof19 eval g711u      | min_dcf           |    -1.044 |      200 |       200 |                  89   |                 61.5 |            29 |                38.4 | lcnn8_distil |
| ASVspoof19 eval g711u      | eer               |     0.113 |      200 |       200 |                  86.5 |                 49   |            29 |                37   | lcnn8_distil |
| ASVspoof19 eval amrnb_4k75 | far1              |     3.365 |      200 |       200 |                   5   |                  2   |            33 |                36.1 | lcnn8_distil |
| ASVspoof19 eval amrnb_4k75 | min_dcf           |    -1.044 |      200 |       200 |                  76.5 |                 50   |            33 |                33.9 | lcnn8_distil |
| ASVspoof19 eval amrnb_4k75 | eer               |     0.113 |      200 |       200 |                  56.5 |                 29.5 |            33 |                38.5 | lcnn8_distil |
