# Synthetic Reference Room: Personal Early-Reflection Prototype

Candidate C keeps the synthetic direct renderer and adds only the personal four-path early-reflection field. It is opt-in and does not replace production.

## Construction

- Extract each raw BRIR path from +4 to +30 ms relative to its own direct peak, with smooth 0.75 ms fade-in and 5 ms fade-out windows.
- Keep LL, LR, RL, and RR distinct so reflection direction and interaural differences survive.
- Apply a causal fourth-order Linkwitz-Riley high-pass at 250 Hz to the reflection branch only. This prevents delayed room energy from changing B's clean bass while retaining the externalization band.
- Align each reflection field to B's theoretical direct peak. Old absolute propagation time and latency are not retained.
- Omit the measured late tail after 30 ms. This isolates whether early personal room structure restores externalization.

## Listening question

Does C move the phantom sources in front of the listener without reintroducing muddy bass or an obvious reverberant effect? If yes, the next version can replace these measured early arrivals with theory-derived reflection taps while preserving the useful binaural structure.
