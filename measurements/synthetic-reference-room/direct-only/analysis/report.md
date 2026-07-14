# Synthetic Reference Room: Personal Direct Prototype

This opt-in control renderer contains a symmetrized personal direct HRTF and no measured room tail. It is not the production default.

## Construction

- Smoothly window each measured path from −3 ms through +4 ms around its own direct peak; the first repeatable room cluster starts after +5 ms.
- Geometrically average LL/RR and LR/RL magnitudes to remove unverified left/right measurement asymmetry.
- Use the accepted renderer only as a broad sub-300 Hz magnitude reference so bass quantity does not become an A/B confound.
- Reconstruct causal minimum-phase direct and cross filters; no measured arrival time survives.
- Delay only the contralateral path by 12.534 samples (0.261 ms), calculated for a ±30° speaker angle and 8.75 cm head radius.

## Interpretation

This version is expected to sound drier and less externalized than the production renderer. Its purpose is to validate the personal direct-HRTF anchor and theoretical timing before synthetic early reflections and a shared late field are added.
