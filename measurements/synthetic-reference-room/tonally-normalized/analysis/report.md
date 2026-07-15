# Candidate I Tonally Normalized Mastering Room

Candidate I preserves H's complete room renderer and direct-only reference. It applies one causal minimum-phase tonal filter to both paths from each virtual speaker, correcting only the 1/6-octave-smoothed complete-to-direct binaural energy ratio from 200 Hz to 1 kHz.

## Mathematical Target

- Left speaker: `(abs(H_LL)^2 + abs(H_LR)^2) / (abs(D_LL)^2 + abs(D_LR)^2)`.
- Right speaker: `(abs(H_RL)^2 + abs(H_RR)^2) / (abs(D_RL)^2 + abs(D_RR)^2)`.
- Each target is the log-frequency mean of its original smoothed ratio, preserving average band quantity.
- The correction is unity below 160 Hz and above 1.25 kHz, with tapered transitions into the 200 Hz-1 kHz normalization band.
- Raw comb-filter teeth, direct HRTF magnitude, relative arrival times, and within-speaker interaural ratios are not independently inverted.

## Offline Result

- Left-speaker RMS coloration falls from 1.294 to 0.414 dB; peak-to-peak falls from 5.850 to 2.248 dB.
- Right-speaker RMS coloration falls from 1.282 to 0.341 dB; peak-to-peak falls from 6.035 to 1.702 dB.
- I-minus-H bass RMS at 20-80 Hz: 0.0005 dB.
- I-minus-H protected upper-band RMS at 1.25-8 kHz: 0.0007 dB.
- Maximum within-speaker ILD change: 0.0532 dB.
- Maximum within-speaker phase change: 0.6388 degrees.
- Modeled maximum correlated renderer gain: +2.62 dB.

I is an opt-in listening candidate. H remains unchanged and A remains the production default.
