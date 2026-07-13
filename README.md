# PhantomDSP

PhantomDSP is an experimental Equalizer APO configuration for reproducing a personalized, speaker-like binaural sound field over headphones. It uses a four-path binaural room impulse response (BRIR) matrix—each virtual speaker measured at both ears—plus headphone compensation, tonal shaping, and a hybrid low-frequency path.

The active BRIRs were measured from JBL LSR305 near-field monitors in a real room. Additional equalization is intended to move their tonal balance toward a JBL M2-inspired reference. This does not reproduce every physical characteristic of an M2, such as directivity, maximum output, or distortion.

## How It Works

The renderer aims to reproduce at the listener's ears what the measured speakers produced there. In simplified form, the digital filter is:

```text
renderer = speaker-to-ear response × inverse headphone-to-ear response
```

The physical headphone supplies its response again during playback, ideally leaving the desired speaker-to-ear response. The BRIR includes intentional propagation delay, interaural differences, early reflections, and room decay; a flat or minimum-delay digital output is not the target.

See [Signal-Chain Architecture](docs/architecture.md) for the complete matrix and measurement assumptions. Planned validation and experiments are tracked in the [DSP Roadmap](docs/roadmap.md).

## Project Status

This repository reflects a personalized research system and includes historical experiments. The active configuration currently targets a 48 kHz stereo endpoint and a Focal Elex profile. Device names, headphone profiles, gain, and routing must be reviewed before use.

The bass path and several spatial-EQ decisions are under active evaluation. Preserve a low listening level when enabling or editing the configuration: Equalizer APO applies saved changes immediately.

## Requirements and Installation

1. Install [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) on Windows and restart if prompted.
2. Copy this repository into `C:\Program Files\EqualizerAPO\config`.
3. In `config.txt`, change the `Device:` selector to the intended output endpoint.
4. In `config - personalized.txt`, select the appropriate headphone correction and disable unrelated profiles.
5. Configure the endpoint for 48 kHz when using the active JBL convolution WAVs.
6. Begin playback quietly and confirm that Equalizer APO reports no configuration or convolution errors.

The repository contains profiles or experiments for several headphones, including the Sennheiser HD650/HD6XX, HD800S, and IE800; Audeze LCD-2 variants; Focal Elear and Elex; Fostex TH-X00; NAD Viso HP50; and others. Their age and validation level vary.

## Important Limitations

- The BRIR is individualized to one listener, room, seat, head orientation, and microphone placement. Spatial accuracy will vary for other listeners.
- Static BRIR playback does not respond to head movement.
- The measured room is part of the rendered sound, including both useful spatial reflections and unwanted room coloration.
- The current configuration has no automatic fallback for an incorrect sample rate or channel layout.
- The approximately 5 ms figure refers to direct-sound arrival in the active IRs, not total application, driver, or device latency.

## Credits

Thanks to Warren Tenbrook, Tyll Hertsens, Harman International, and Paul Barton for research and work that informed the project.
