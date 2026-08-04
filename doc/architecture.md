# AlifeAmbience - architecture and method

AlifeAmbience is two systems over the untouched engine soundscape for S.T.A.L.K.E.R.
Anomaly / G.A.M.M.A. The ATMOSPHERE system gathers the dark, dreadful, and mournful
sounds from several soundscape packs, measures each one, and composes two of its own
layers (texture + accent) on top of whatever ambient setup is installed, using DLTX. The
DIEGETIC system owns the volume of the in-world sound the game already emits (base radios,
megaphones, campfire instruments) by wrapping the engine's physical-sound path. Neither
replaces the ambient system: one layers onto it, the other tunes what is already there.

This document is the method and the invariants. The build tool is `tools/merge.py`;
every number below is reproduced by a subcommand of it, not chosen by hand.

## Atmosphere model: enrich the engine's own channels, don't parallel them

The engine primitive is the CHANNEL (`sound_channels.ltx`): a named channel with
settings (distance, four periods, indoor, height) and a `sounds=` list; presets switch
channels on per (level, time, weather) section via `sound_channels_dynamic`. AlifeAmbience
adds two layers, split by how a sound behaves, decided per file by measurement (below):

- TEXTURE - continuous LOOPED beds (drones, whispers, fog, wind, rain, tunnels). One bed at a time by context, low, crossfaded. `xr_sound.play_sound_looped` + `set_volume_sound_looped`, native volume, no engine hook. Driven by `gamedata/scripts/aa_texture.script`, six pools: wind, dread, fog, stormrain, and underground split lab vs sewer.
- ACCENT - dynamic ONE-SHOT scares. Instead of shipping its own parallel channels, AlifeAmbience works ON the engine's own channels, via DLTX `@[channel]` (safe create-or-override) with `>sounds` (append), routed per source channel:
  - ENRICH - a channel BOTH installs play (`out_spooks`, the `ugrnd_*` set, `out_drone`, ...): append our net-new sounds to it. No new channel, no preset change, no added density - it already plays where the base plays it, now with more variety.
  - RESTORE - a channel vanilla plays but the GAMMA winner (Dark Signal) STRIPS (`out_mutants`, `out_screams`, `out_gunfire`): define it + re-add it to the presets, restoring the horror GAMMA removed.
  - DEFINE - a purpose no live base channel provides (forest creaks, rain, the distant spook variants, creeping wind): our own self-contained `aa_<channel>` with full settings, placed in the presets. Install-independent, so it behaves the same on Anomaly and GAMMA.

Why this shape: parallel `aa_acc_*` channels (the old model) DUPLICATED sounds the base
already plays and doubled the section density. Enriching the base channels eliminates both
- the base plays each purpose on ONE channel, richer, and only restore/define add to the
section count (capped, below). A channel keeps its real name; `mood`-in-the-name is gone.

Full engine + Lua mechanics with `file:line` are in the stalker-dev library note
`doc/library/anomaly/internals/ambient-sound-system.md`.

## Content pipeline (reproducible)

`tools/merge.py` is a six-stage pipeline; each stage is a subcommand that reads the
previous stage's committed artifact and writes the next. A pack change is a re-run,
not a rewrite.

```
basedex    what the install PLAYS (md5+fingerprint) -> base_index.json
plan       source trees, minus base-dups            -> merged_channels.json
classify   measured signal features per sound       -> classification.json
loudness   per-group median leveling (outliers)     -> loudness_outliers.json
deploy     channels + layer map + DLTX presets       -> gamedata/
ledger     content-hash proof of coverage           -> ledger.tsv
provenance every shipped file -> its origin          -> provenance.tsv
```

- basedex (`cmd_basedex`): index every sound the install PLAYS, winner-resolved - vanilla's active channels (unpacked from `sounds_ambient.db0`) + the GAMMA winner (Dark Signal) active channels, EXCLUDING its stripped channels (those are ours to restore). Records md5 + Chromaprint fingerprint + duration per sound. Rebuilt when the install's ambient mods change.
- plan (`cmd_plan`): pool each dark channel's sounds and walk the FOLDER TREES (`DARK_FILL`), because the packs ship far more dark content than any channel references; resolve, gate on codec+rate, then DEDUP each channel to one copy per distinct recording - md5, then Chromaprint to propose candidates, then PCM cross-correlation to decide (see Deduplication below). Then BASE-DEDUP: drop any sound the install already plays (`_base_dedup`), fingerprint-matched and cross-correlation-confirmed against the winner-resolved base index. Output `merged_channels.json`, the net-new dark corpus.
- classify (`cmd_classify`): measure every pooled sound and assign its role (below).
- loudness (`cmd_loudness`): measure integrated loudness and flag per-group outliers (below).
- deploy (`cmd_deploy`): route each source channel enrich/restore/define (above), emit the audio to `zs\<channel>\N.ogg`, the DLTX `mod_sound_channels_alifeambience.ltx` (channel defs), `aa_channel_layers.ltx` (the channel->layer map), and the per-preset placement, and the texture pools. Deterministic - the shipped `N.ogg` numbering is a pure function of the JSON inputs, so provenance is recoverable.
- ledger (`cmd_ledger`) and provenance (`cmd_provenance`): the proofs (below).

## Measurement and signal analysis (the techniques)

Role is not guessed from a channel name. Each sound is measured with signal-analysis
CLIs and classified on the measured values.

Feature extraction, per file, one `ffprobe` + one `ffmpeg` pass:

| Feature | Tool / filter | Meaning |
|---------|---------------|---------|
| duration | `ffprobe` stream duration | bed vs one-shot length |
| spectral centroid | `ffmpeg aspectralstats=measure=centroid` | brightness (Hz) |
| spectral flatness | `ffmpeg aspectralstats=measure=flatness` | tonal (near 0) vs noise-like (near 1) |
| crest factor | `ffmpeg astats` | peak-to-RMS: transient (high) vs steady (low) |
| integrated loudness | `ffmpeg ebur128` (I, LUFS) | EBU R128 program loudness |
| sample rate / codec / bitrate | `ffprobe` | fitness gate + dedup tiebreak |

Measured role decision (`_classify_one`):
- duration >= 30 s -> TEXTURE (a bed); duration < 4 s -> ACCENT (an event).
- otherwise TEXTURE iff crest < 12 AND flatness < 0.40 (steady and non-transient), else ACCENT.
- VOCAL channels (screams, spooks, mutant calls) are FORCED to accent regardless of length: a wail is an event, never a loop.
- brightness label from centroid (dark < 2000 Hz < mid < 4000 Hz < bright); tonality label from flatness (tonal < 0.15 < mixed < 0.40 < noisy). Recorded for inspection.

Proof the split is real, not nominal: a drone measures 181 Hz centroid / 0.04
flatness (dark, tonal, steady -> texture) against a scream at 1276 Hz and tonal but
short and transient (-> accent), and wind at 7658 Hz (bright, noisy).

Deduplication - identity is decided by the WAVEFORM, not the filename or the bytes.
Three stages, cheapest first, so the expensive test only runs on the few pairs the
cheap ones flag (`dedup_pick` in `merge.py`, `pcm_correlation`/`decode_pcm` in `soundpool.py`):
- md5 (exact): byte-identical reships across packs collapse to one.
- Chromaprint fingerprint (recall, `fpcalc`, >= 0.88): PROPOSES candidate same-sound pairs. It is stable across bitrate and codec, so it FINDS the re-encoded copies md5 misses - but it cannot DECIDE. Measured on this corpus, its same-vs-distinct similarity ranges overlap completely: a genuinely distinct sound can score 1.000 (two different rains) and a true re-encode 0.926. At NO threshold does the fingerprint separate them; used to decide it merges distinct screams and distant calls.
- PCM cross-correlation (the decider, `DEDUP_XCORR` = 0.90): for each candidate pair, decode both to PCM, align by envelope offset (so a Vorbis priming shift or a silence-pad difference cannot defeat it), and take the normalized cross-correlation over the overlap. A re-encode correlates ~1.0, a distinct sound ~0 - a clean gap. Two files merge only under COMPLETE-LINKAGE - every pair in a merged group confirms - so a similarity chain (A~B~C, A!=C) cannot collapse transitively. Ground-truthed against the decoded waveforms: zero distinct sounds merged (MANGLE = 0).

The SAME three-stage identity guards base-dedup (never ship a sound the install already plays): a candidate the fingerprint matches to a base sound is dropped only when the cross-correlation confirms it, so a distinct sound the fingerprint wrongly flags is KEPT, not lost. The base index therefore records md5 + fingerprint + duration + path, so the confirm step can decode the base sound. The intra-corpus and base thresholds are the same waveform test applied to two ends: keep every distinct variant, drop every genuine re-encode, byte or not.

Loudness leveling: per group (channel/bed) take the MEDIAN integrated LUFS as the
group level, and gain back only the OUTLIERS - files where |LUFS - median| >
max(6, 1.5 x IQR). Everything inside the band is shipped verbatim (no re-encode, no
quality loss); outliers are re-encoded with `ffmpeg volume=<median-LUFS>dB`,
preserving dynamics. This is deliberately NOT a global normalize: slamming a whisper
and a scream to one level would flatten the mix. On the measured data 148 of 2596
(6%) are outliers; the rest ship untouched.

Fitness gate: 44100 Hz vorbis only (the X-Ray standard); off-rate and junk-bitrate
files are dropped and accounted (never silently).

## Distribution: evidence-driven, per (level, time, weather)

The vanilla ambient section name carries both time (`day`/`evening`/`morning`/
`night`) and weather (`rain*`, `pre_storm`, `storm_*`, `tuman*`) plus the indoor set.
Only RESTORE and DEFINE channels are placed (`write_presets`); ENRICH channels already
play wherever the base plays them, so they are never re-placed. Placement is TRACED from
how the pack authors used the sounds, not invented:

- For each of our 21 level presets and each section, a restore/define channel plays iff a source author placed its source channel in that exact level+section. The section name is time+weather, so night-heavier-dread, animals-by-time (crows by day, owls at dusk/night) and weather-gating fall out of the source placement.
- Two lore overrides, cross-checked against S.T.A.L.K.E.R. canon: the underground labs (`environment_underground`/`_more`/`_x18`) get underground-layer channels in indoor sections only; the haunted `environment_whisper` drops wildlife and people.
- DENSITY BUDGET: the placed channels are capped so the winner's base channel count + our additions never exceeds `SECTION_MAX` (13, vanilla's observed per-section ceiling). Over budget, channels drop by `LAYER_ORDER` - dread-core kept, wildlife and rain first out. Because enrich adds no channels, the total tracks a vanilla-like density.
- D1 FLOOR NORMALIZATION: on VANILLA the fake-horror channels GAMMA already strips (`out_screams`/`out_mutants`/`out_gunfire`/`wind_dark`) are removed per section via DLTX `<sound_channels_dynamic` wherever we do not restore them, so vanilla's denser base drops to the GAMMA floor and the one budget (computed vs the GAMMA winner) holds on both installs. No-op on GAMMA (those channels are already absent); a channel we restore in a section is never both stripped and re-added there. Measured: GAMMA avg 8.2 / max 13 / 0 over; vanilla avg 9.1 / max 13 / 0 over (20 over before D1).

Every placed and enriched channel maps to one of 11 LAYERS (`aa_channel_layers.ltx`,
generated from `layer_of`): spooks, screams, mutants, ambience, machines, forest, storm,
wind, rain, wildlife, underground. The layer is the pure-purpose group; it drives the
per-layer MCM volume and the density budget. It is DATA in the map, never encoded in a
channel name (`aa_sound` reads it via `r_string_ex`). The map also lists the base's OWN
dark channels the install plays (e.g. `ugrnd_voices`, `x18`, base `storm`), so a layer's
volume governs the WHOLE dark soundscape - base channels and ours together, not only our
additions.

## Play tuning and no-repeat variety

The verbatim source settings are the crystallized baseline (kept in `provenance.tsv`); the
DEPLOYED play is then evolved so a big corpus is actually heard, not 10% of it 90% of the
time. Two mechanisms:

- BUILD-TIME period tuning (`_tune_period`, define channels): the played period is set `>= sound duration + a gap` so a long sound never overlaps itself (a 12s storm on a 5s period is a wall, not an accent), then scaled by channel size so a thin channel fires proportionally less (its handful is spread, not spammed) while a rich channel keeps the discrete rate. Storm 5000 -> 21000 ms; the 3-sound night ambience 10000 -> 64200 ms. This is why the source period and the deployed period differ - provenance holds the source, git holds the evolution.
- RUNTIME no-repeat (`aa_sound.pick_sound`): because the mod owns the play loop, each channel keeps a ring of its last few picks and re-rolls until one is fresh, so a channel never replays a recent sound - never the same call twice, even in a channel placed across many sections. A default-on MCM toggle; off falls back to base random. The recent window is capped below the sound count, so the pick always terminates.

The texture bed follows context at runtime (`aa_texture.script`): underground (engine
`underground` event) - splitting the lab pool from the sewer pool by `level.name()`
against the game's own X-Lab level names - then weather (storm/rain, then fog), then
time of day (the dread drone-bed dusk-to-dawn, the lighter wind-bed by day, via
`level.get_time_hours()`).

## Provenance and proof

- `provenance.tsv` (`cmd_provenance`): every shipped `N.ogg` -> original mod, directory, filename, source channel, that channel's LTX `min/max_distance`/`period0-3`/`indoor`/`height`, the gain applied, and the exact list of original `level:time:weather` sections it played in. Nothing loses its origin under the `N.ogg` rename.
- Self-verification: the deterministic deploy is re-derived and every VERBATIM shipped file is md5-compared to its claimed source. Current build: 1066 verbatim match, 0 mismatch (the gained files differ by design) - the rename is proven lossless and the provenance exact.
- `ledger.tsv` (`cmd_ledger`): hash every source ogg against the deployed set and categorise: USED-shipped, USED-gained, HELD-texture-surplus, EMISSION-excluded, BASE-DUP-excluded (the install already plays it - md5 or cross-correlation), INTRA-DUP-excluded (our own re-encode the PCM dedup dropped - captured then deduped, not missed), OFFSPEC-48k-excluded, off-scope-or-dup, SKIP-nonambient, and UNUSED-DARK. The invariant: **UNUSED-DARK = 0** - no NET-NEW dark file (one the install doesn't play) is left uncaptured. Current: UNUSED-DARK 0, BASE-DUP-excluded 3644, USED-shipped 1310, HELD 269, EMISSION 279, INTRA-DUP-excluded 177, USED-gained 92, OFFSPEC 1.

## Numbers (current build)

- Base-played index: 1155 sounds the install plays (vanilla + GAMMA winner active).
- Pooled 5487 -> deduped 2304 (md5, then Chromaprint candidates confirmed by PCM cross-correlation; the PCM stage caught 177 acoustic re-encodes md5 kept) -> BASE-DEDUP dropped 590 md5 + 123 cross-correlation-confirmed the install plays -> 1487 NET-NEW dark sounds kept.
- Classified: 980 accent, 507 texture (vocals forced accent).
- ACCENT: 44 channels - 10 enrich (into base channels), 3 restore (`out_mutants`/`out_screams`/`out_gunfire`), 31 define (`aa_<channel>`). No parallel mood channels; each channel keeps its real name and its VERBATIM source settings. Every channel maps to one of 11 layers via `aa_channel_layers.ltx`.
- Placement: restore/define channels placed per evidence + lore (restore evidence includes vanilla's own presets, so a strip-4 channel only vanilla placed - out_screams - is still re-added), density-capped to `SECTION_MAX` 13; with D1 both installs hold within the cap (max 13, 0 over). Enrich channels add sounds, not channels, so they carry no density cost.
- Textures: each bed deduped across its pooled source channels (same waveform identity), then capped to TEX_CAP so the cap keeps distinct loops, not repeats.
- Layer map: 47 our channels + 14 base-played dark channels = 61 mapped, so per-layer volume covers the whole dark soundscape.
- Play tuning: deployed periods are discrete (>= duration + gap) and variety-weighted; storm's play share dropped 33% -> 20%. Runtime no-repeat variety is default-on.
- TEXTURE: 6 looped pools - wind, dread, fog, stormrain, underground_lab, underground_sewer - up to 40 loops each by duration (196 total; fog ships 16).
- Provenance self-verify: 1155 verbatim match, 0 mismatch.

## Invariants

- I1 Compose, never override. Ship DLTX patches over the ambient config; the engine bed and its asserted channels stay intact, so an overlay cannot cause a missing-channel CTD.
- I2 Two layers, split by measurement. Texture = looped bed; accent = dynamic one-shot; the boundary is the measured duration/crest/flatness, not the name.
- I3 Deduplicate by the WAVEFORM. Identity is md5 (exact) -> Chromaprint fingerprint (recall: it finds re-encodes but its same/distinct ranges overlap, so it cannot decide) -> PCM cross-correlation (the decider: a re-encode correlates ~1.0, a distinct sound ~0), complete-linkage at 0.90. Distinct variety is never merged (MANGLE = 0); a genuine re-encode never survives.
- I3b Never ship a sound the install already plays. Base-dedup drops a sound only when the fingerprint matches AND the cross-correlation confirms it, against the winner-resolved base-played index (vanilla + GAMMA), so no duplication on either install, byte or re-encode - and a distinct sound the fingerprint wrongly flags is kept.
- I3c Work ON the engine's channels, not beside them. Enrich a channel both installs play, restore one the winner strips, define a new one only for a purpose no live base channel provides; never parallel a channel the base already plays.
- I4 Fitness is codec + sample rate: 44100 Hz vorbis. Off-spec files are dropped and accounted.
- I5 Loudness by per-group median leveling, outliers only. Preserve dynamics; texture beds sit below accents; distance varies at play.
- I6 Capture from folder trees, not just channel-wired files. The proof that this matters is the ledger: it is what drives UNUSED-DARK to 0.
- I7 Distribution is traced from the source configs, refined by canon for the specials, then density-capped to vanilla's per-section ceiling. No flat map; no random placement; no density blow-up.
- I7b The channel -> layer map is the single control axis. One layer per channel (data, not name); the layer drives both the MCM volume and the density budget. 11 layers, fixed; channel count is free.
- I8 Variety is free. A channel/bed may hold as many sounds as pass I3/I4; the surplus beyond a bed cap is held and accounted, never dropped.
- I9 Dark scope only. Keep dread/horror/underground/eerie/oppressive-weather; leave generic daytime life to the base ambience.
- I10 Leave emission alone. Blowout and psi-storm are their own system.
- I11 Reproducible. plan -> classify -> loudness -> deploy -> ledger -> provenance regenerates the whole overlay from the packs.
- I12 Traceable. Every shipped sound resolves to its origin via `provenance.tsv`; every source file resolves to a ledger category. Credit every source pack (author + link) in the readme.
- I13 Runtime control owns only while a feature is active. Per-layer knobs, the trace, and no-repeat variety take the vanilla play slot only when active and hand it back otherwise. `_apply_owned` is the SOLE owner of the slot; the clone never self-removes (a channel-less section leaves it ticking harmlessly, not dead).
- I14 Pass-through is reachable. Turn no-repeat variety off with every knob at 1.0 and the trace off, and the mod hands the slot back to vanilla untouched. No-repeat variety is DEFAULT-ON, so out of the box the clone owns the loop - a small always-on cost for the variety it buys.
- I15 Diegetic sets volume from the base, never a read-back. The diegetic layer computes `volume = base * mult` from the section condlist each tick; it never reads the value it last wrote and multiplies again, which would compound frame to frame against ph_sound's 50ms throttle.
- I16 Crystallize the verbatim, evolve the play. The source settings are kept exactly in `provenance.tsv`; the deployed period is tuned (discrete `>= duration + gap`, variety-weighted by channel size) so the corpus is heard, not 10% of it 90% of the time.
- I17 Never the same sound twice. The owned play loop keeps a per-channel ring of recent picks and re-rolls until fresh; the window is capped below the sound count so the pick always terminates.
- I18 One floor on both installs (D1). On vanilla the fake-horror channels GAMMA strips are removed per section wherever we do not restore them, so a single density budget holds on vanilla and GAMMA alike. A restored channel is never both stripped and re-added in the same section.
- I19 The owned clone never blocks or plays out of context. It resets on hour, LEVEL, or weather change (a sound never fires on the wrong level), and guards every value an engine call needs: nil/zero period, missing distance, empty sounds, nil actor, nil weather manager.

## Tools and data artifacts

- Signal analysis: `ffmpeg` (`aspectralstats` centroid/flatness, `astats` crest, `ebur128` loudness, `volume`+`libvorbis` gain), `ffprobe` (duration/rate/codec/bitrate). Dedup identity: md5 (exact) -> Chromaprint `fpcalc` (recall) -> PCM cross-correlation (`pcm_correlation`, the decider). Chromaprint proposes, the waveform decides. Resolved from `$PORTX_ROOT/packages` by `soundpool.py`.
- Committed data (the audit trail): `merged_channels.json` (pool + per-channel source LTX), `classification.json` (measured features + role per sound), `loudness_outliers.json` (the gained set), `ledger.tsv` (coverage proof), `provenance.tsv` (origin of every shipped sound), `pools.json` (legacy candidate registry for the standalone `soundpool.py`; the authoritative source list is `merge.py` MODS).
- `merge.py` the pipeline (its `MODS` list is the source of truth); `soundpool.py` the probe/resolver (helper functions used by `merge.py`; its `inventory`/`select` CLI over `pools.json` is legacy).

Adopting a pack: refresh it on disk, add it to `merge.py` MODS (the authoritative
source list), re-run the pipeline, read the ledger (UNUSED-DARK must stay 0) and the
provenance self-verify (0 mismatch). Nothing is added by hand.

## Deploy

A DLTX overlay: it can sit anywhere in load order and still compose. Wired via
`stalker-manager` (a `repo:` external for local sync, a `git:` external for the
gamma-redux install). Distributed as a GitHub release / moddb; the repo holds the
buildable source (tool + docs + the audio).

## Runtime control, trace, MCM

Scripts add control, an in-game trace, and the MCM over both systems, mirroring the
alife-family pattern (`at_mcm`/`at_debug`/`xmcm`/`xlog`). All are guarded: without xlibs
they degrade to no-ops and the mod runs content-only on any Anomaly. `_aa_deps.script` is a
SOFT xlibs check (`is_compatible`, family deps format): it warns when xlibs is present but
older than the floor, and never aborts, so a stock install still runs content-only.

- `aa_sound.script` (Atmosphere) owns the dynamic-ambient play whenever a feature is active - and no-repeat variety is default-on, so it normally owns. The vanilla one-shot loop is `sound_ambient.update_ambient`, a `CreateTimeEvent` action dispatched by stored function value (`_g.script:374`) into an EMPTY slot only (`:345`), with no callback and file-local state (`snd_chanels`/`next_idx`/`opt`) no other script can read. The only Lua path in is `RemoveTimeEvent` then `CreateTimeEvent` of a faithful clone (own state, public API only) with per-layer volume/rarity/distance knobs, the no-repeat picker, and trace at the vanilla injection points. Each played channel's layer comes from `aa_channel_layers.ltx` (`r_string_ex`), so even a base channel the mod merely enriched is volume-controlled. The clone is stricter than vanilla for correctness (I19): it resets on hour, LEVEL, or weather change (vanilla resets on hour only, so a same-hour level load leaves the old level's channels), it NEVER self-removes the slot (`_apply_owned` is the sole owner - a channel-less section ticks harmlessly instead of killing the layer), and it guards every value an engine call needs (nil/zero period, missing distance, empty sounds, nil actor, nil weather manager). GAMMA runs the vanilla script unmodified (verified). Pass-through is reachable (I14): variety off + knobs neutral + trace off hands the slot back.
- `aa_diegetic.script` (Diegetic) owns the in-world audio. It wraps `ph_sound.snd_source.update` (core script; present on vanilla and the Anomaly Radio Extended override), classifies each emitter by its theme (radio / megaphone / other, cached per source), and after calling the original sets the played sound's volume to `base * mult` - where `base` is the section condlist volume, recomputed each tick, NOT the value last written. Reading back the written volume compounds frame to frame: the binder updates per frame (`bind_physic_object.script:45-55`) but ph_sound rewrites volume only on its own 50ms throttle, so `volume = volume * mult` sawtooths; computing from the condlist base is stable (I15). Instruments have no volume seam upstream - `guitar_anim.play_guitar` bakes volume into a local no-feedback play (`guitar_anim.script:45-50`) - so it replaces `play_guitar`/`play_harmonica` with one parameterized helper. Neutral is pass-through: at mult 1.0 the emitter is left to vanilla.
- `aa_debug.script` is the trace facade (mirrors `at_debug`): one logger, one integer gate. At DEBUG it records every accent (level, section, channel, layer, file, distance, volume) to `alifeambience.log`, so the soundscape is checked by observation and an Anomaly run diffs cleanly against a GAMMA run. Below DEBUG the off path marshals nothing and crosses no luabind bridge.
- `aa_mcm.script` is one MCM page tree with two tabs, Atmosphere and Diegetic (the at_mcm `_key_to_tab` + nested `path_builder`; the saved path is `aa/<tab>/<key>` and matches the tree). Atmosphere: per-layer volume (11 layers) plus a global, rarity, distance, texture volume, no-repeat variety, trace log level. Diegetic: master plus per-source volume/enable/frequency for radio, megaphone, guitar, harmonica. Every control is 1.0 = pass-through. Labels in EN + RU (`configs/text/{eng,rus}/ui_st_mcm_aa.xml`, windows-1251 for RU).

## Future (not built)

A demonized-exe callback at the engine static-bed play site, registered through the xlibs
fallback, to extend per-mood control to the C++ background bed. Not required for the current
model: texture volume is native and accents are levelled and controllable through the clone.
Planned content: original sounds recorded for this mod and scripted event sequences.

## Baseline (measured 2026-08-02)

Reference values measured from vanilla Anomaly + GAMMA soundscape mods + the source packs,
not hand-chosen. `src: tested`. Parallel channels per place (`sound_channels_dynamic` length
per level preset x time):

| Source | Places | Avg | Median | p90 | Max |
|--------|--------|-----|--------|-----|-----|
| vanilla Anomaly | 72 | 9.7 | 9 | 12 | 13 |
| Soundscape Overhaul | 240 | 5.6 | 5 | 8 | 11 |
| Dark Signal Weather | 240 | 5.6 | 5 | 8 | 11 |
| RETUNE | 241 | 6.6 | 6 | 11 | 13 |
| Dark Signal Amplified | 349 | 5.7 | 5 | 8 | 11 |

Ceiling 13 (vanilla max, no pack exceeds it); target avg ~10. The old full-override build
peaked at 26 (the overload to avoid). Dark-channel settings (n=223 defs): min_distance 2..120
(median 45), max_distance 3..300 (median 80), periods median 10000/15000/14000/26000 ms.
Loudness (187 sampled sounds): -60.3..-12.8 LUFS, median -32.6, stdev 10.4; within-channel
spread up to 17 LUFS, which is why leveling is per-group median, outliers-only. Measured by
`merge.parse_presets` (counts), `merge.parse_channels` (settings), `ffmpeg ebur128` (loudness).

### Vanilla vs GAMMA horror delta (measured 2026-08-03)

Vanilla places fake horror in nearly every ambient section; GAMMA (Soundscape Overhaul, the
horror-stripper) removes it. Measured over the preset sections (`ambients/presets/environment_*.ltx`):

| Baseline | channels/section (avg / max) | horror/section (avg) | fauna/section |
|----------|------------------------------|----------------------|---------------|
| vanilla | 9.7 / 13 | 4.9 | 0.85 |
| GAMMA (Soundscape Overhaul) | 5.6 / 11 | 2.4 | 0 |

Strip/restore delta - horror channels vanilla places that GAMMA drops: `out_screams`,
`out_mutants`, `out_gunfire`, `wind_dark` (the fake mutant/scream ambience). GAMMA KEEPS the
subtle dread (`out_spooks`, `out_drone`, `out_dark_amb`, + the underground set) and removes
fauna-as-horror (crows/owls/dogs) from ambient entirely. So the overlay DLTX-strips those four
on vanilla to reach GAMMA's floor (a no-op on GAMMA, already gone), keeps GAMMA's subtle dread,
and restores CURATED horror back toward vanilla density (~5 horror/section, target ~10 total)
with real sounds instead of the fake screams/mutants.

## Per-area distribution profile (canon x placement)

Placement is evidence-driven (`write_presets._section_moods`: a mood plays in a level+section
iff a source pack placed a channel of that mood there), refined by S.T.A.L.K.E.R. canon for the
specials. The evidence agrees with canon on 19 of 21 levels; the 2 overrides are underground
labs (indoor sections only) and whisper (dread + weather, no wildlife/people).

| preset | canon area / terrain | human | atmosphere | placement |
|--------|----------------------|-------|------------|-----------|
| cemetary | Truck Cemetery - rusted vehicle graveyard | light | eerie, exposed | dread+weather+animal+light human |
| darkscape | Darkscape - dark wooded rocky valley | light (bandits) | oppressive, dim | dread-heavy+animal+weather |
| field | open fields (Cordon/Agroprom) | moderate | windswept | full |
| forest | forested levels - dense canopy | moderate | enclosed | dread+animal+human, less weather |
| garbage | Garbage - junkyard reclaimed by nature | moderate (bandits) | desolate | full |
| generators | Generators - irradiated forest+industrial | Monolith | irradiated, tense | dread+human heavy+weather, some crows |
| hospital | Pripyat/Limansk hospital interior | none (ghost) | claustrophobic, decay | dread+human+light animal, low weather |
| jupiter | Jupiter (CoP) - factory+fields+underground | heavy | industrial, mixed | full incl human |
| npp | Chernobyl NPP - reactor, Monolith | Monolith | irradiated, dark | dread+human heavy+weather, some crows |
| pripyat | Pripyat - overgrown ghost city | Monolith | haunting ruin | dread+human+animal, low weather |
| pripyat_outskirts | Pripyat approach - ruin + field edge | Monolith/loner | ruin, exposed | as pripyat |
| rostok | Rostok/Bar - Duty hub, industrial urban | HEAVY (safe hub) | populated, industrial | human+dread+animal (dread rarer here - future) |
| rostok_wild | Wild Territory - industrial ruins | mercs (light) | ambush, tense | dread heavy+human+animal+night spoops |
| swamp | Great Swamps - marsh, water, fog | light (Clear Sky) | foggy, wet, eerie | full+weather(fog) heavy+animal |
| underground | generic tunnels/sewers/catacombs | none | dripping, claustrophobic | underground only, indoor |
| underground_more | more tunnel variants | none | claustrophobic | underground only |
| underground_x18 | Lab X18 - dark lab, poltergeists | none | darkest, psi, machinery | underground only |
| urban | Dead City / Limansk ruins | mercs/Monolith | desolate urban | dread+human+animal, low weather |
| whisper | haunted whisper level | none | HAUNTED, whispering | dread+weather only (override) |
| yantar | Yantar - dead lake/swamp, bunker, zombies | Ecologists+zombies | PSI, sickly, foggy | dread(psi)+human(sci drones)+weather+animal |
| zaton | Zaton (CoP) - dried swamp, shipwrecks | loners/bandits | desolate wetland, foggy | full+weather+animal |

Texture bed selection (`aa_texture.script want_bed`, one pool audible at a time): underground
(engine event) splits LAB pool on the X-Lab level names vs SEWER pool elsewhere; then weather
(storm/rain > 0.3 -> stormrain, foggy/tuman -> fog); then time of day (dusk-to-dawn dread bed,
daylight wind bed). The lab/sewer split is per-CLASS, not per-level (per-level would be invented).
