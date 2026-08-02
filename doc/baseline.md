# AlifeAmbience - derived baseline

All values below are measured from the real data (vanilla Anomaly + GAMMA
soundscape mods + the source packs), not chosen by hand. They are the reference
the build and the runtime layer tune toward. `src: tested`. Measured 2026-08-02.
Re-derive with the commands in "How measured".

## Parallel channels per place

`sound_channels_dynamic` list length per place (level preset x time).

| Source | Places | Avg | Median | p90 | Max |
|--------|--------|-----|--------|-----|-----|
| vanilla Anomaly | 72 | 9.7 | 9 | 12 | 13 |
| Soundscape Overhaul | 240 | 5.6 | 5 | 8 | 11 |
| Dark Signal Weather | 240 | 5.6 | 5 | 8 | 11 |
| RETUNE | 241 | 6.6 | 6 | 11 | 13 |
| Dark Signal Amplified | 349 | 5.7 | 5 | 8 | 11 |

Ceiling = 13 (vanilla's own max; no pack exceeds it). Target average ~10. The old
full-override build peaked at 26 = the overload to avoid.

## Channel settings

Dark channels across all sources incl. myRETUNE/Antares (n = 223 channel defs).

| Setting | Min | Max | Avg | Median |
|---------|-----|-----|-----|--------|
| min_distance | 2 | 120 | 42 | 45 |
| max_distance | 3 | 300 | 81 | 80 |
| period0 (ms) | 0 | 120000 | 20753 | 10000 |
| period1 (ms) | 0 | 300000 | 50915 | 15000 |
| period2 (ms) | 0 | 180000 | 27803 | 14000 |
| period3 (ms) | 0 | 360000 | 59126 | 26000 |

Baseline distance 45 / 80; each channel keeps its own value clamped to this range.
Baseline periods = the medians above.

## Loudness

Integrated LUFS over 187 sampled dark sounds (from `merged_channels.json`, the
5-pack content build).

| Metric | Value |
|--------|-------|
| Min | -60.3 LUFS |
| Max | -12.8 LUFS |
| Avg | -34.1 LUFS |
| Median | -32.6 LUFS |
| Stdev | 10.4 LUFS |

Within-channel spread reaches 17 LUFS (e.g. `background_wind_storm` -33..-16),
`underground_background_2` 17, `urban_debris` 13. That inconsistency is why the
sounds must be loudness-normalized.

Normalization is per-group and outliers-only, NOT a global target. Slamming every
sound to -33 would flatten the mix (a whisper and a scream at one level is wrong).
Instead: within each channel/bed take the median LUFS as the group's level, and
gain back only the sounds sitting outside a band around it (the whack ones, like a
-16 in a -33 group). Everything within the band stays verbatim (no re-encode, no
quality loss). Roles stay leveled apart: texture beds low, accents higher; distance
varies each at play. The -33 median is a reference, not a target to force onto every
file. On the measured data the outliers are a small set (the 17 LUFS spreads in
`background_wind_storm`, `underground_background_2`, `urban_debris`), not the 1466.

## Derived decisions

- Density ceiling 13 / target 10 (I6).
- Distance baseline 45 / 80, per-channel clamped to the measured range (I5).
- Period baseline = the medians (I5).
- Loudness: per-group median leveling, outliers-only (gain only the whack sounds back toward their group; keep the rest verbatim; texture beds lower than accents; distance varies at play).

## How measured

- Channel counts: `merge.parse_presets` per source, `len(sound_channels_dynamic)` per section.
- Distances / periods: `merge.parse_channels` over all source gamedata, dark channels only, numeric parse of the setting lines.
- Loudness: `ffmpeg -af ebur128 -f null -` integrated LUFS over a per-channel sample of `merged_channels.json`.
