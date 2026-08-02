# AlifeAmbience - architecture

A dark-mood ambient overlay for S.T.A.L.K.E.R. Anomaly / G.A.M.M.A. It merges the
dark, dreadful, and mournful sounds from several soundscape packs into one curated
layer and adds them on top of whatever ambient setup is installed, using DLTX. It
does not replace the ambient system; it composes onto it. Curated for dread and
atmosphere, not generic daytime life.

This document is the method and the invariants. The build tool is `tools/merge.py`.

## What it is, in one line

Take every soundscape pack's channels, keep only the dark/horror/dreadful/sad ones,
merge them (best-quality copy per sound, duplicates and junk removed), harmonize how
many play at once, and inject them over the base ambience via DLTX.

## Why an overlay, not an override

DLTX composes onto `environment/sound_channels.ltx` and the ambient presets: it can
add new channel sections, fill empty ones, and append to the sound and layer lists,
all without replacing the base file (confirmed in-game 2026-08-02; engine loads
these via CInifile, which is DLTX-aware). So AlifeAmbience:

- Layers on top of any ambient mod (GAMMA's, vanilla, another soundscape) instead of overriding it.
- Ships only its own dark content, not a full copy of the ambient system.
- Cannot cause a missing-channel CTD, because the base stays intact.
- Stays portable and modest in size.

## Model: three layers

1. Presets (`configs/environment/ambients/presets/*.ltx`) - per place (map + time), which channels play (`sound_channels_dynamic`).
2. Channels (`configs/environment/sound_channels.ltx`) - what each channel is: its `sounds` list plus distance/period.
3. Sound files (`sounds/...`) - the audio.

The curation signal: each source pack already sorts every sound into a channel;
that assignment is the curation. AlifeAmbience reuses it rather than guessing by
folder name.

## Pipeline (tools/merge.py)

- plan - parse every source pack's `sound_channels.ltx`. For each channel, pool every sound any pack assigns, resolve to real files, dedup by exact content hash (identical reships collapse; distinct sounds never merge), drop off-spec (non-44100) and junk-bitrate files. Keep only channels in the DARK SCOPE. Compute each channel's settings by the SOFTEST + RAREST rule. A channel whose curated content does not resolve (out_mutants) is filled from a declared source. Output: `merged_channels.json`.
- presets - parse every pack's presets. For each place, union the dark layers, filter to channels we ship, and HARMONIZE (cap layers per place to a sane density). Output: `merged_presets.json`.
- deploy - emit a DLTX overlay: `mod_sound_channels_alifeambience.ltx` (add dark channels with `@[...]`, fill/enrich with `![...]` + `>sounds`), `mod_<preset>_alifeambience.ltx` files that append dark layers per place, and copy the dark sound files into `sounds/`. No full `sound_channels.ltx`, no preset replacement.

## Invariants

- I1 Compose, never override. Ship DLTX patches, not full copies of the ambient config.
- I2 Curation from each pack's channel assignments, not folder-name guessing.
- I3 Dedup by exact content hash. Acoustic fingerprinting proved unreliable on short one-shot sounds (it merged 25 distinct screams to 4), so it is not used.
- I4 Fitness is codec + 44100 Hz. Off-spec files are dropped.
- I5 Settings by softest + rarest across the unmuted definers: min_distance and max_distance = the largest any pack uses (farthest, quietest placement), periods = the largest (rarest firing), muted definers ignored, single definer used as-is.
- I6 Harmonize density. No place plays more layers than a real mod does (target near vanilla's ~10, never the raw union).
- I7 Dark scope only. Keep dark/horror/dreadful/sad/negativistic channels; drop generic daytime life (birds, insects, plain wind, pleasant beds), which the base ambience already provides. Leave emission alone.
- I8 Copy verbatim, never re-encode (a size-driven bitrate cap is a separate, optional release step).
- I9 Reproducible: plan -> presets -> deploy regenerates from the source packs; a pack change is a re-run.
- I10 Credit every source (author + link) in the readme.

## Dark scope

Kept: dread cues (spooks, screams, mutant growls, dark ambience, dark_signal), all
underground, tension (distant gunfire, ominous drones, creeping wind, branch creaks),
eerie atmosphere (owls, dogs, crows, fog), and oppressive weather (storms, rain,
howling wind). Dropped: daytime birdsong, insects/bugs, plain wind, pleasant tree
and foliage rustle, and the neutral base beds. Emission is left to its own system.

## Deploy

Wired in `stalker-manager/gamma-redux.yaml` as a `path` external. As a DLTX overlay
it can sit anywhere in load order and still compose. Distributed as a GitHub Release
zip and/or moddb; the repo holds the buildable source (tool + docs), with the sound
files either committed (if trimmed under the GitHub size guidance) or attached to a
release.

## Source and status

Built from four packs (Dark Signal Weather, Dark Signal Amplified, Soundscape
Overhaul, RETUNE) plus vanilla for channel coverage. The prior full-override build
(Zone Soundscape, in `GammaExternal/`) is kept as a reference; this repo is the
overlay rebuild. Credits and per-source detail in `readme.txt`.
