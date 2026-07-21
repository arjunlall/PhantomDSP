# Phantom Project Context and DSP Invariants

## Purpose and Authority

Read this document before changing the renderer, headphone calibration,
measurement research, runtime architecture, profile format, or product claims.
It is the compact operating context for both repositories:

- `/Users/arjun/dev/PhantomDSP`: the personalized Equalizer APO prototype,
  Windows runtime oracle, renderer-generation history, and forensic evidence;
- `/Users/arjun/dev/phantom`: the portable product, research contracts,
  generated-profile architecture, future DSP core, and plug-in work.

This is intentionally a decision document, not an experiment diary. Historical
candidate letters are mentioned only where needed to identify the selected
artifact. Detailed reports remain available in PhantomDSP when a result must be
audited.

This file is intentionally mirrored byte-for-byte in both repositories. Update
both copies together. A newer accepted ADR may supersede part of this document;
if so, update this synthesis rather than allowing it to become an attractive but
stale source of truth.

Current anchors verified on 2026-07-21:

| Repository | Role | Verified state |
| --- | --- | --- |
| `PhantomDSP` | Equalizer APO oracle and renderer evidence | `codex/dsp-improvements` at `b75097a`; Candidate M activation was committed at `4b5a5a3` |
| `phantom` | Portable product and calibration research | `main` at `4a247d6` |

These commits are evidence anchors, not a substitute for checking the live HEAD
and worktree before making changes.

## The Product in One Sentence

Phantom makes ordinary stereo headphones resemble a stable pair of loudspeakers
in a controlled room by combining one fixed 2x2 binaural speaker renderer with
graded headphone calibration, bounded preference controls, and explicit safety
gain.

It is not merely crossfeed, not merely headphone EQ, not a generic room reverb,
and not a claim to reproduce every physical property of a JBL M2 or any other
loudspeaker.

## The Fundamental Transfer-Function Model

The desired two-speaker-to-two-ear response is a complex matrix:

```text
        input speaker
          L       R
ear L   B_LL    B_RL
ear R   B_LR    B_RR
```

The physical headphone-to-ear transfer is approximately diagonal:

```text
P = diag(P_L, P_R)
```

With personal calibration, the desired digital transfer is approximately:

```text
C_personal = inverse(P_personal) x B

ear output = P_personal x C_personal x stereo input
           ~= B x stereo input
```

This explains an easy-to-make mistake: the electrical DSP output is not
supposed to look flat in isolation. The physical headphone completes the
transfer. Flattening the final digital output can erase the loudspeaker and
spatial response the system is intended to produce.

The physically correct execution relationship is:

```text
stereo input
  -> source-format validation
  -> 2x2 spatial renderer
  -> ear-side headphone calibration
  -> bounded preference controls
  -> safety gain / output adaptation
  -> physical headphone
```

The matrix order matters. Headphone compensation left-multiplies the renderer:

```text
C = E_ear x B
```

An identical common model EQ on both channels can commute through the matrix.
Independent personal left/right filters cannot. If ear-side filters are fused
into the renderer assets, apply the left-ear filter to `LL` and `RL`, and the
right-ear filter to `LR` and `RR`. Applying a left/right personal inverse to the
stereo inputs before the matrix would instead attach the filters to virtual
speakers and change the wrong paths.

Some product diagrams list calibration before rendering as a logical inventory
of layers. Do not interpret that presentation order as permission to violate
the matrix multiplication above. Linear filters may be fused when mathematically
valid, but their roles and actual path ownership must remain separate in
manifests, tests, controls, and reasoning.

## The Frozen Reference Renderer

The selected source lineage is historically called Candidate M or the Presence
Balanced Room Renderer. Its product identity is:

```text
phantom-reference-renderer-v1
```

It is the fixed starting reference for universal, model-aware, and personal
headphone modes. Do not retune the room per headphone. If a headphone needs a
different correction, fix or qualify the headphone-calibration layer. A changed
renderer response requires a new semantic renderer version and an explicit
decision record.

### Exact Assets

| Virtual speaker asset | Format | SHA-256 |
| --- | --- | --- |
| `Synthetic Reference Room/IRs/presence-balanced/Presence Balanced Room Left Speaker.wav` | Stereo, 48 kHz, 24-bit PCM, 32,768 frames | `d3c4b41e15c08edbb9cef737d1d92713ea73fddda1931f058c7d5e68c719dea7` |
| `Synthetic Reference Room/IRs/presence-balanced/Presence Balanced Room Right Speaker.wav` | Stereo, 48 kHz, 24-bit PCM, 32,768 frames | `d47c20d7eeb9fa5eab8dffc53382427bebe93d9dde69286a178f0437c4c41d56` |

The left-speaker WAV contains `LL` then `LR`. The right-speaker WAV contains
`RL` then `RR`. Equalizer APO calls the right-input paths `RIL` and `RIR`, but
their meaning is the same:

```text
LL  = left input  -> left ear
LR  = left input  -> right ear
RL  = right input -> left ear
RR  = right input -> right ear

left output  = convolve(left input, LL) + convolve(right input, RL)
right output = convolve(left input, LR) + convolve(right input, RR)
```

This is a true 2x2 matrix. A single crossfeed filter, two diagonal headphone
filters, or one stereo reverb cannot substitute for it.

### What Is Frozen and What Is Not

Frozen in renderer v1:

- the final four complex paths represented by the two WAVs;
- their relative gain, polarity, phase, and timing;
- virtual-speaker geometry and the balance of direct, early, diffuse, and late
  energy encoded in those paths;
- the unified spatial low-frequency behavior;
- the broad per-speaker room-tonality treatment;
- the directional allocation and timbre of the diffuse early field.

Not part of the renderer:

- Focal Elex flattening;
- owner-specific left/right balance;
- the root target/preference macro, including its currently active +2 dB shelf
  at 80 Hz in the personal Equalizer APO chain;
- a public-database headphone profile;
- the unknown-headphone population prior;
- device names, Windows endpoints, DAW state, or measurement routing;
- safety preamp, bass preference, or brightness preference.

The source Equalizer APO configuration includes some of those downstream stages
after the renderer. That complete personal chain is an oracle and listening
reference, not the portable product package.

## Why Each Renderer Component Exists

### Direct Sound Establishes Direction, but Is Not Enough

The direct paths carry the intended roughly +/-30 degree speaker directions,
interaural time and level differences, and pinna/head filtering. The selected
renderer inherits a regularized personal direct-HRTF lineage, with common
propagation delay omitted while relative direct/cross timing is retained.

Direct sound by itself produced frontal but headphone-like presentation. It did
not create convincing monitor distance. Therefore a future worker must not
reduce Phantom to an HRTF filter or crossfeed network simply because the direct
paths look like the most obvious localization mechanism.

### Low Frequencies Belong to the Spatial Image

Bass localization and speaker attachment depended on the complex interaural
behavior and group delay through roughly 80-200 Hz. Cleaner-looking parallel
low-pass/high-pass experiments weakened the frontal bass image and pulled bass
back toward the headphones.

The accepted architecture therefore uses one causal full-band 2x2 renderer with
a smooth extended low-frequency model inside all four paths. It does not use a
separately delayed clean-bass branch or a runtime bass crossover. Bass quantity
is adjusted later with a common preference shelf, not by replacing the spatial
bass topology.

Do not judge this region from mono magnitude alone. Check correlated stereo,
all four complex paths, relative delay, upper-bass transients, and listening
placement.

### Early Energy Creates a Plausible Binaural Room

Distinct early energy begins a few milliseconds after the direct sound and is
important through approximately 25-30 ms. The accepted synthetic room contains
controlled specular reflections plus deterministic diffuse microclusters.

Perfect bilateral sample identity was deliberately rejected. A symmetric early
field with correlation near 1.0 pulled centered material toward the forehead.
The accepted field keeps left/right center energy balanced while using distinct,
partially decorrelated waveforms; the mastering-room design achieved maximum
broadband early correlation around 0.168 and less than 0.001 dB center-energy
mismatch.

The goal is plausible, bounded asymmetry, not arbitrary channel imbalance.
Discrete 1-8 kHz specular arrivals remain well below direct sound; the accepted
design measured them at least 13.36 dB down.

### Sustained Late Energy Creates Apparent Distance

Early paths alone still sounded too close. Restoring controlled binaural energy
after approximately 30 ms restored monitor distance and spaciousness. The
accepted deterministic late field was derived from a broad perceptual target:
approximately 0.565 seconds of decay, nearly equal late energy at both ears, low
coherence above 500 Hz, and a retained-early-to-late energy ratio around 9.16 dB.

The late field is present on purpose. Removing it to reduce the IR to a few taps
changes the product. It should be shortened or altered only through a new,
controlled renderer experiment with distance and externalization checks.

### Room Tonality Is Corrected Broadly, Not Made Anechoic

Room energy naturally creates comb filtering. Inverting each narrow tooth would
be fragile, placement-specific, and likely to add extreme filters. The renderer
instead uses one broad correction per virtual speaker, applied identically to
both ear paths from that speaker. This preserves the speaker's interaural ratio
while reducing audible coloration.

The retained broad treatment normalizes complete-to-direct coloration mainly
from 200 Hz to 1 kHz, then removes a remaining broad 1-1.5 kHz jump with a smooth
transition beginning near 900 Hz and returning to unity by about 1.8 kHz. It
does not flatten the personal direct HRTF and does not invert raw comb-filter
teeth.

### Directional Diffuse Energy Needs Both Ear Allocation and Timbre

The early diffuse microclusters are not generic stereo noise. Their energy is
modeled as approximately 80% horizontal side field, 10% floor, and 10% ceiling.
From roughly 3-14 kHz, public directional HRTF deltas inform how each speaker's
existing smoothed microcluster power is divided between the ears. The model is
fully active from about 4-12 kHz.

The fused power of each virtual speaker is preserved while the ear allocation
changes. Multiplying raw HRTF deltas onto the branch would double-count head
shadow and change tonality.

Directional allocation alone left the diffuse field too bright because it
omitted monitor directivity and treated-surface high-frequency loss. The final
renderer attenuates only the microcluster branch in the 6-10 kHz region, using a
common causal minimum-phase filter for both ear paths from each speaker. The
selected presence-balanced response delays the attenuation entrance through
approximately 5.5-7.5 kHz so string articulation is retained, while preserving
the accepted upper treatment above 7.5 kHz.

## Frequency and Time Map

These numbers have different semantic owners. Do not turn them into one global
EQ curve.

| Region | Owner | Intent |
| --- | --- | --- |
| 20-40 Hz | Headphone calibration | Best-effort, capability-aware model correction; not a promise that every headphone is flat to 20 Hz |
| 40-100 Hz | Headphone calibration | First reliable model-aware correction objective when compatible evidence exists |
| Roughly 80-200 Hz | Spatial renderer | Preserve spatial bass attachment, complex interaural behavior, and transient continuity inside the 2x2 matrix |
| Below roughly 250 Hz | Synthetic room branches | Protect the spatial bass model by high-passing room-only reflections; this does not remove direct or modeled bass |
| 200-350 Hz | Specular-room treatment | Reduce broad coherent floor/side-wall cancellation without changing the rest of the room |
| 200 Hz-1 kHz | Renderer tonality | Broad per-speaker complete-to-direct normalization; never narrow comb inversion |
| 900 Hz-1.8 kHz | Renderer tonality | Smooth correction of the remaining 1-1.5 kHz room-coloration step |
| 3-14 kHz | Spatial renderer | Directional diffuse-field ear allocation; full strength is roughly 4-12 kHz |
| 5.5-7.5 kHz | Spatial renderer | Presence-balanced entrance to microcluster attenuation so articulation is not over-damped |
| 6-10 kHz | Spatial renderer | Treatment/directivity-aware diffuse-field timbre correction |
| Above roughly 6-10 kHz | Headphone calibration | Preserve the complete compatible model response or robust population center; report fixture, fit, and anatomy limitations as evidence rather than a gain taper |
| Approximately 4-25 ms | Spatial renderer | Distinct early reflections and diffuse energy |
| Approximately 25-30 ms | Spatial renderer | Controlled transition from early field to late decay |
| After approximately 30 ms | Spatial renderer | Sustained low-coherence late energy that supports apparent distance |

The same frequency can appear in more than one row because the layers answer
different questions. For example, an 80 Hz user shelf changes bass quantity;
the renderer's 80-200 Hz complex response determines whether that bass remains
attached to the virtual speakers.

## Deliberate Exclusions and Guardrails

The following are absent on purpose:

| Do not add or assume | Reason |
| --- | --- |
| One generic crossfeed filter instead of four paths | It cannot reproduce path-specific direction, spectrum, timing, reflections, and decay |
| Independent peak alignment of LL/LR/RL/RR | It destroys meaningful interaural and interspeaker timing |
| Implicit IR normalization, trimming, polarity repair, or resampling | Relative gain, time, and phase are part of renderer identity |
| A delayed parallel clean-bass branch | It produced phase/cancellation problems and weakened spatial bass attachment |
| Narrow inversion of room comb teeth | The notches are fragile and are part of a time-domain room response, not stable broadband coloration |
| Elex or personal left/right filters in the renderer | They describe one headphone/listener, not the virtual speakers |
| Root target/preference macro baked into the renderer | Preference must remain adjustable and reversible |
| Population prior stacked with an exact model profile | Exact-model selection replaces the population prior |
| One mixed over-ear/in-ear population prior | Form factor, insertion, targets, and operating states differ |
| Arbitrary global 50% correction strength | It conflates target identity with uncertainty and does not estimate a population |
| Silent fixture conversion | Raw and derived curves from different fixtures are not interchangeable |
| Silent sample-rate coercion | The frozen IR is 48 kHz; other rates require explicit, deterministic generated assets or visible rejection |
| Measurement-only Equalizer APO selectors during playback | They can bypass or isolate renderer branches and produce a misleading active chain |
| Dozens of room/HRTF controls in the initial UI | The product needs one coherent reference and a safe default, not an experiment browser |
| System-audio capture inside the DSP core | Device routing, permissions, and recovery belong to host/platform adapters |

Absolute common delay may be removed or reduced only when the same operation is
applied to all four paths and relative timing is proven unchanged. A causal
renderer can reduce arrival latency but cannot have zero total application and
device latency.

## Headphone Calibration Is a Separate Product Layer

Phantom supports three levels while retaining the same renderer.

### Universal / Unknown Headphone

Unknown mode cannot know the exact physical headphone transfer. Its intended
composition, written here as addition of frequency-response curves in dB, is:

```text
E_unknown,c,dB(f) = B_phantom,dB(f) + Q_population,c,dB(f)
```

Do not confuse the inherited name `B_phantom` with the renderer matrix `B` used
earlier in this document. `B` is the four-path complex spatial transfer;
`B_phantom` is a same-for-both-ears target-translation curve. They are separate
objects despite the notation collision.

- `B_phantom` is the versioned translation from a compatible neutral fixture
  coordinate to the Phantom reference.
- `Q_population,c` is the separate full-band robust center of complete
  compatible profile responses for a declared headphone cohort such as
  over-ear products.

The first five-product wireless over-ear population estimate is experimental,
not a shipping default. Its active identity is
`phantom-population-prior-v1-experimental` under
`phantom-population-prior-package-v2`. It evaluates every published OPRA filter
from 20 Hz to 20 kHz, removes only arbitrary constant offset, and takes the
equal-weight pointwise median. It applies no post-median smoothing, Q rejection,
frequency taper, confidence multiplier, global strength factor, or magnitude
cap. Cohort median absolute deviation and range are factual evidence only.

### Model-Aware

For a supported exact model and operating state:

```text
E_model,h,dB(f) = B_phantom,dB(f) + Q_model,h,dB(f)
```

`Q_model,h` replaces `Q_population,c`; it is never stacked on top. A compatible
OPRA model profile preserves the complete published response, including upper-
frequency and higher-Q filters, while excluding its constant gain. Model
correction is normally identical for both channels unless trustworthy channel-
specific source data exists. Unit variation, pad wear, seal, position, ANC,
firmware, codec, and wireless DSP remain limitations.

### Personal

Personal mode uses independent left/right headphone-to-ear measurements and can
most closely realize the reference. Personal channel balance is allowed only as
an explicit personal stage, not hidden inside the renderer or a model-average
profile.

Original headphone REW `.mdat` projects, raw left/right traces, reseats,
microphone calibration, and fit metadata are preferred inputs. The current
research can proceed from classified historical flatten curves and compatible
public data; private raw measurements are opened only when a named evidence
problem requires them. Original speaker-to-ear `.mdat` files are useful for
forensics and closed-loop validation but are not a prerequisite for headphone
generalization because renderer v1 is already frozen.

## Target, Population, and Preference Must Not Be Confused

The current `B_phantom` work is an experimental target translation, not a frozen
consumer target. In the pinned InnerFidelity coordinate, its broad shape closes
closely against the negative normalized Harman over-ear 2018 target. That result
confirms sign and coordinate behavior—including reversal of the Harman bass
preference shelf and fixture/pinna ear gain—but does not prove that every OPRA
profile shares the coordinate or freeze Harman as the Phantom target.

The current working research coordinate uses a passing `autoeq_oratory1990`
family containing HD 800 S, HD 650, a provisional pre-2017 LCD-2 pairing, and
measurement-era Elear. This is trusted estimator evidence, not independent
validation. `B_phantom` remains full-band with its existing 1/6-octave working
smoothing; independent model/family checks remain open.

Preference is simpler and later in the chain:

- bass quantity and broad brightness/tilt are bounded user controls;
- the owner's active +2 dB shelf at 80 Hz is personal preference evidence, not
  part of `phantom-reference-renderer-v1` or `B_phantom`;
- preference controls must not change interaural ratios or room timing;
- a preference change must be reversible without regenerating the renderer or
  pretending the reference target changed.

## Measurement Data and Database Policy

- Fixture identity is part of every measurement. GRAS, B&K 5128, HMS,
  InnerFidelity, in-ear microphones, and derived OPRA coordinates cannot be
  mixed silently.
- Exact product variant and acoustic state matter: pads, revisions, ANC,
  connection, firmware, and wireless mode are not cosmetic metadata.
- Raw measurements are research evidence. The user-facing catalog should expose
  stable product identities, compatibility, factual evidence, and attribution
  rather than raw database layout.
- OPRA can anchor a portable derived-profile catalog. AutoEq remains useful for
  research and source discovery. HUTUBS provides population checks for HD 800 S
  and HD 650. None of these makes fixtures interchangeable.
- Third-party redistribution rights must be recorded before raw data or profiles
  are bundled. Personal ear measurements are private by default.
- Raw-measurement generation still must not blindly invert reseat-sensitive
  notches. That guardrail does not justify deleting upper-frequency or higher-Q
  filters from an already derived and regularized compatible OPRA profile.
- A frequency-response curve alone cannot prove distortion, excursion,
  maximum SPL, or safe playback level.

## Gain, Headroom, and Physical Capability

Positive correction is preserved when justified; digital clipping is handled
with calculated negative pre-EQ gain rather than silently weakening the target.
The current experimental population package follows that rule.

That calculation is not the complete product answer. Final headroom must include:

- the correlated sum of all four renderer paths;
- target translation;
- universal, model, or personal headphone correction;
- maximum allowed preference controls;
- switching/crossfade behavior;
- output adaptation and any declared limiting policy.

Candidate M's existing Windows report records no clipping or configuration
errors, 5.13 dB correlated-sweep headroom, and approximately 0.61-0.67% maximum
single-core CPU. The selected activation was not rerun locally on macOS, and the
dedicated raw Candidate M capture package still needs to be located or
recaptured before the portable project claims independently archived runtime
validation.

Digital headroom does not prove that a headphone can reproduce a boost cleanly.
The current low-frequency policy aims for reliable compatible correction through
40 Hz and treats 20-40 Hz as capability-aware best effort. Model-specific
distortion or output evidence—not an arbitrary universal boost ceiling—must
justify stronger physical limits.

## Runtime and Product Architecture

The portable product owns one framework-independent `PhantomDSPCore`:

```text
versioned runtime package
          |
          v
   PhantomDSPCore
     /         \
offline runner  VST3 first
                  \
             later AU / native / hardware adapters
```

The first real-time product route is a stereo VST3 loaded in a VST3-capable DAW.
The DAW owns routing and the physical device. A VST3 is contained, but it is not
system-wide audio by itself. Audio Unit, a native Mac system-audio shell, and a
Raspberry Pi or CamillaDSP backend are later adapters that must pass the same
four-path conformance contract.

The framework and implementation language are not yet accepted decisions.

The runtime minimum for the renderer is the two frozen WAVs plus a semantic
manifest containing routing, format, latency, gain, hashes, and compatibility.
Python generators, HRTF datasets, REW projects, Equalizer APO configs, and
historical candidates are reproducibility or forensic dependencies—not audio
callback dependencies and not required inside the plug-in bundle.

The real-time callback must not allocate memory, perform file I/O, parse
metadata, build filters, resample IRs, wait on unbounded locks, log
synchronously, or throw across a host boundary. Package loading and validation
happen off-thread; the audio thread receives immutable prepared state through a
bounded transition.

The first release is exact 48 kHz. Other sample rates must either fail visibly
or use deterministic off-thread resampling that creates separately validated
artifacts. Silent rate mismatch is forbidden.

## Validation Vocabulary and Current Evidence Boundary

Use these labels exactly:

- **offline validated:** files, routing, arithmetic, response constraints, or
  deterministic generation passed without executing the intended live host;
- **runtime validated:** the intended engine/host loaded and processed probes
  correctly;
- **acoustically validated:** the physical headphone output was remeasured;
- **listening evaluated:** listening conditions, level matching, listener count,
  and blinding status are recorded.

Candidate M is:

- frozen by asset hash and offline analysis;
- reported as runtime validated through Equalizer APO Benchmark;
- selected through the owner's informal sighted listening and physical-monitor
  comparison;
- not yet proven acoustically through a complete closed-loop headphone capture;
- not yet proven population-general across listeners or anatomies.

The experimental target translation and population prior are offline research
artifacts only. Their deterministic regeneration and composition reports are
not a portable-core execution, not complete-chain headroom, not a predicted
eardrum response, and not a selected runtime default.

Never turn a plot, static file inspection, source-family fit, or one listener's
preference into a stronger claim.

## Change Protocol for Future Workers

Before changing anything:

1. Check the live repository HEAD, branch, worktree, and applicable `AGENTS.md`.
2. Identify the semantic owner of the proposed change: renderer, target
   translation, population prior, exact-model profile, personal calibration,
   preference, safety, core, or host adapter.
3. State the hypothesis and the one variable intended to change.
4. Verify active source paths and hashes. In PhantomDSP normal playback must
   contain exactly one renderer include: `Presence Balanced Room Renderer.txt`.
5. Preserve the original assets. Never overwrite a frozen WAV or raw capture.
6. Compare all four paths, not only averaged left/right magnitude. Include
   relative timing, polarity, phase/complex response, and correlated summation.
7. Calculate headroom for the complete affected chain and test left-only,
   right-only, correlated, channel-ID, silence, clipping, and bypass probes as
   applicable.
8. Keep measurement-only routing out of normal playback and restore Candidate M
   after historical captures.
9. Run the relevant deterministic tests and distinguish macOS/offline evidence
   from Windows/host evidence.
10. Update manifests, hashes, validation labels, ADRs, and both copies of this
    document when a decision changes.

Do not modify renderer v1 merely because a profile, target, or headphone sounds
wrong. First bypass the headphone layer, preference layer, and renderer
independently; verify fixture compatibility and level matching; then attribute
the problem to the correct layer.

## Current Open Decisions and Work

These are intentionally unresolved:

- storage policy and byte-for-byte migration of the two renderer WAVs into
  `phantom`;
- dedicated raw Windows capture or recovery for the active Candidate M chain;
- population generality of the personal direct-HRTF lineage and whether a later
  HRTF option/version is justified;
- final `B_phantom` target manifest, independent holdouts, and diffuse-field
  comparison;
- validation of the over-ear `Q_population` before it becomes the unknown-mode
  default, plus separate future in-ear research;
- exact model profiles and at least one physical closed-loop measurement;
- complete-chain headroom and preference limits;
- runtime-package schema, core lifecycle, convolution implementation, and
  plug-in framework;
- supported DAWs, sample rates, Audio Unit route, native Mac shell, head
  tracking, and hardware backend.

Unresolved does not mean unconstrained. New work must preserve the invariants in
this document while collecting the evidence needed to make the next decision.

## If You Remember Only Twelve Things

1. Phantom is one fixed loudspeaker-like 2x2 spatial reference plus increasingly
   precise headphone calibration.
2. The four complex paths and their relative timing are the renderer; crossfeed
   is not an equivalent shortcut.
3. Candidate M is frozen as `phantom-reference-renderer-v1` by the two exact WAV
   hashes above.
4. Direct HRTF cues establish direction, early binaural coherence stabilizes the
   image, and post-30 ms late energy creates apparent distance.
5. Bass must stay inside the unified 2x2 matrix; quantity is a separate common
   preference control.
6. Correct room coloration broadly per virtual speaker; never invert narrow comb
   teeth or independently alter its two ear paths.
7. The renderer contains no Elex inverse, personal balance, target macro,
   population prior, or device routing.
8. Universal target translation and population correction are separate;
   exact-model selection replaces rather than stacks the population prior.
9. Fixture, variant, pad, seal, ANC, firmware, and measurement role are part of
   the data contract.
10. Digital headroom, transducer capability, acoustic closure, runtime closure,
    and listening preference are different kinds of evidence.
11. The portable order is shared core, offline conformance, then VST3 in a DAW;
    system-wide and hardware products come later.
12. When something sounds wrong, isolate the layer before changing the frozen
    renderer.

## Detailed Sources When an Audit Is Necessary

Use this document for orientation, then consult the relevant source of truth:

### PhantomDSP

- `docs/architecture.md`: transfer model and accepted DSP findings;
- `docs/ir-manifest.md`: exact renderer assets and hashes;
- `docs/current-status.md`: concise experimental conclusions and validation;
- `docs/synthetic-mastering-room-plan.md`: geometry, coherence, reflection,
  normalization, directional, and timbre rationale;
- `docs/synthetic-reference-room.md`: full renderer lineage when forensic detail
  is actually necessary;
- `measurements/synthetic-reference-room/presence-balanced/analysis/`: Candidate
  M numerical evidence;
- `tools/measurement/`: generators, tests, and Windows capture tooling.

### Phantom

- `docs/product.md`: user experience, promises, and scope;
- `docs/architecture.md`: product transfer functions and semantic layers;
- `docs/renderer.md`: frozen renderer contract and generalization questions;
- `docs/calibration.md`: target and personal/public measurement methodology;
- `docs/population-prior.md` and
  `docs/population-prior-v1-experimental.md`: unknown-headphone architecture and
  current evidence; `docs/population-prior-v0-experimental.md` is superseded
  historical evidence;
- `docs/low-frequency-policy-v0.md`: model correction below 100 Hz;
- `docs/runtime-strategy.md`: core, package, plug-in, and host contract;
- `docs/transition-inventory.md`: exact migration slices and source hashes;
- `docs/decisions/`: accepted architectural decisions;
- `docs/roadmap.md`: current gates and unresolved work.
