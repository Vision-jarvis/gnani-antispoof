# Indic pilot: FLEURS bona fide vs IndicSynth FreeVC (G4), Hindi + Kannada, n = 600 bona fide / 600 spoof

## EER % per channel condition
| condition         |   aasist |   aasist_l |   gmm16_clean |   gmm8_aug |   lcnn8_aug |   lcnn8_noaug |   ssl_aasist |
|:------------------|---------:|-----------:|--------------:|-----------:|------------:|--------------:|-------------:|
| clean16k          |    50    |      50    |         40.14 |     nan    |      nan    |        nan    |        49.92 |
| nb_pcm            |    50    |      50    |         49.79 |      24.49 |       45.01 |         49    |        49.92 |
| g711u             |    49.2  |      47.58 |         49.96 |      19.35 |       39.94 |         49.87 |        49.62 |
| amrnb_12k2        |    49.92 |      49.87 |         49.92 |      32.98 |       50    |         50    |        44.03 |
| amrnb_4k75        |    48.77 |      45.14 |         50    |      26.07 |       48.92 |         50    |        27.38 |
| gsm_fr            |    50    |      49.96 |         50    |      19.87 |       46.08 |         49.7  |        47.05 |
| chain_amrnb_g711u |    47.95 |      46.57 |         49.96 |      18    |       47.61 |         50    |        48.81 |

## FRR % at the ASVspoof-dev threshold for FAR = 1%
| condition         |   aasist |   aasist_l |   gmm16_clean |   gmm8_aug |   lcnn8_aug |   lcnn8_noaug |   ssl_aasist |
|:------------------|---------:|-----------:|--------------:|-----------:|------------:|--------------:|-------------:|
| clean16k          |    54.17 |      66.33 |         99.33 |     nan    |      nan    |        nan    |         0.33 |
| nb_pcm            |    69    |      86.83 |        100    |      99.67 |       91.67 |        100    |         2.5  |
| g711u             |    64.83 |      90.5  |        100    |      98.33 |       81.17 |         99.67 |         6.67 |
| amrnb_12k2        |    84.5  |      96.33 |        100    |     100    |       99    |        100    |        17.5  |
| amrnb_4k75        |    97.5  |      99    |        100    |     100    |      100    |        100    |        81.5  |
| gsm_fr            |    89    |      98.33 |        100    |     100    |       99.5  |        100    |        33.33 |
| chain_amrnb_g711u |    78.83 |      96.33 |        100    |      99.67 |       99.33 |        100    |        52.17 |

## EER % per language
|                                |   aasist |   aasist_l |   gmm16_clean |   gmm8_aug |   lcnn8_aug |   lcnn8_noaug |   ssl_aasist |
|:-------------------------------|---------:|-----------:|--------------:|-----------:|------------:|--------------:|-------------:|
| ('hi-IN', 'amrnb_12k2')        |    49.92 |      49.1  |         49.83 |      32.08 |       47.29 |         50    |        38.45 |
| ('hi-IN', 'amrnb_4k75')        |    46.92 |      39.43 |         50    |      23.47 |       41.72 |         49.92 |        34.89 |
| ('hi-IN', 'chain_amrnb_g711u') |    42.22 |      41.85 |         49.92 |      17.43 |       44.85 |         49.83 |        47.01 |
| ('hi-IN', 'clean16k')          |    50    |      50    |         32.95 |     nan    |      nan    |        nan    |        49.74 |
| ('hi-IN', 'g711u')             |    45.51 |      43.32 |         49.92 |      17.91 |       38.54 |         49.74 |        41.35 |
| ('hi-IN', 'gsm_fr')            |    50    |      50    |         50    |      19.05 |       38.94 |         49.75 |        43.2  |
| ('hi-IN', 'nb_pcm')            |    50    |      50    |         49.58 |      24.4  |       36.16 |         48.94 |        49.06 |
| ('kn-IN', 'amrnb_12k2')        |    49.83 |      49.92 |         43.78 |      30.57 |       49.92 |         50    |        46.18 |
| ('kn-IN', 'amrnb_4k75')        |    47.83 |      44.53 |         50    |      25.07 |       50    |         50    |        18.67 |
| ('kn-IN', 'chain_amrnb_g711u') |    48.42 |      49.42 |         44.4  |      20.38 |       49.84 |         50    |        49.19 |
| ('kn-IN', 'clean16k')          |    50    |      50    |         42.76 |     nan    |      nan    |        nan    |        49.75 |
| ('kn-IN', 'g711u')             |    49.41 |      49.5  |         48.67 |      20.84 |       40.91 |         49.66 |        49.92 |
| ('kn-IN', 'gsm_fr')            |    50    |      49.92 |         50    |      20.98 |       49.57 |         49.39 |        46.05 |
| ('kn-IN', 'nb_pcm')            |    50    |      50    |         48.05 |      25.03 |       49.92 |         48.69 |        49.83 |

## Shortcut audit (single cue, best direction; rule: must stay >= 35%)
| cue                                                |   best_direction_eer |
|:---------------------------------------------------|---------------------:|
| silence                                            |                27.71 |
| loudness                                           |                28.31 |
| duration                                           |                16.63 |
| silence (trim gate, 30 dB) (CM input)              |                43.31 |
| silence (gate 20 dB) (CM input)                    |                38.91 |
| silence (gate 25 dB) (CM input)                    |                40.17 |
| silence (WebRTC VAD) (CM input)                    |                35.08 |
| non-speech fraction (WebRTC VAD) (CM input)        |                45.55 |
| low-energy frame fraction (< max-30 dB) (CM input) |                34.83 |
| loudness (CM input)                                |                44.72 |
| duration (CM input)                                |                19.96 |
