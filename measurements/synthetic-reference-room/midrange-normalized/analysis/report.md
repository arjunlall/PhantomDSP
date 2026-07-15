# Candidate J Midrange Normalized Mastering Room

Candidate J preserves I's complete room renderer and direct-only reference. It adds one causal minimum-phase tonal filter shared by both ear paths from each speaker. The combined 200 Hz-1.5 kHz result is evaluated against the direct reference, while J's new correction is confined to the transition around 1 kHz-1.5 kHz.

## Mathematical Target

- Left speaker: `(abs(I_LL)^2 + abs(I_LR)^2) / (abs(D_LL)^2 + abs(D_LR)^2)`.
- Right speaker: `(abs(I_RL)^2 + abs(I_RR)^2) / (abs(D_RL)^2 + abs(D_RR)^2)`.
- J retains I's established 200 Hz-1 kHz target level, so the successful lower-midrange balance is not re-centered.
- The new correction is unity below 900 Hz and above 1.8 kHz, with tapered transitions into the 1 kHz-1.5 kHz normalization band.
- Raw comb-filter teeth, direct HRTF magnitude, relative arrival times, and within-speaker interaural ratios are not independently inverted.

## Offline Result

- Left-speaker RMS coloration falls from 1.848 to 0.437 dB; peak-to-peak falls from 8.872 to 2.294 dB.
- Right-speaker RMS coloration falls from 1.545 to 0.368 dB; peak-to-peak falls from 6.937 to 1.824 dB.
- J-minus-H bass RMS at 20-80 Hz: 0.0005 dB.
- J-minus-H protected upper-band RMS at 1.8-8 kHz: 0.0013 dB.
- J-minus-I RMS at 200 Hz-1 kHz: 0.0164 dB.
- J-minus-I RMS at 1-1.5 kHz: 2.4973 dB.
- Maximum within-speaker ILD change: 0.0517 dB.
- Maximum within-speaker phase change: 0.4030 degrees.
- Modeled maximum correlated renderer gain: +2.61 dB.

J is an opt-in listening candidate. I and H remain unchanged, and A remains the production default.
