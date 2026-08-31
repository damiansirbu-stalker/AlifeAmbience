# AlifeAmbience - architecture and method

AlifeAmbience is the atmosphere soundscape for S.T.A.L.K.E.R. Anomaly: every map, every weather state, every hour plays a living, audible, varied ambience.
It is a curated work. The config is the source of truth, authored by hand: the channels, their pools, the presets, the level bindings.
The pipeline (`tools/merge.py`) is a mastering mill. It materializes, masters, reports, and proves what the config says. It never chooses content.

It is the counterpart to AlifeSpooks. AlifeSpooks owns the horror one-shots and statically vetoes them out of the base ambient channels.
AlifeAmbience owns the continuous nature/weather ambience and the storm thunder. The two never overlap.

## Content model

Dark Signal Amplified Soundscape is the spine, structure and content.
It is the only pack with a complete level/weather config (33 levels, all Atmospherics states, plus the extended maps), and it is the content default for every voice slot.
The spine is curated whole: every ambience-scope file in the pack is kept, re-homed to a better channel, or excluded with a written reason.
That includes content its other sound systems own, such as the thunder corpus of its thunderbolt configs.
"The pack" means all of its sound systems, not only the ambient channels. The narrower definition is how an earlier build lost the entire thunder category to the prune stage without a trace.

Other packs add what the spine lacks or does weakly, always as channels, never as pool filler:

- Soundscape Overhaul: wind. The spine's own wind is muffled, its known weak spot, and SO's measured strongest.
- Audio Expansion: insects and frogs, content the spine does not have.
- Immersive Ambience: helicopter and wind reinforcement.
- Thunder, rebuilt from the spine's thunderbolt corpus plus SO's and AE's thunder folders.
  The distant rumble plays as storm-state ambient channels, and the close claps play through the lightning-strike system at the vanilla strike paths.
- The standalone builds (Dead Air, NLC, OGSE, Prosector, Solyanka, SoP) are mined for specific missing voices only. An original-game recording beats a mod's re-edit at equal quality.
- Every other pack in the corpus (the RETUNE lineage, RAO, the S2 packs) is a bench. A family enters only by clearly beating the current holder of its slot, by measurement and by ear.

Sources are the registry `tools/sources.py`: one entry per pack (name, path, url, licence, role).
A licence gate stops the build on any source not cleared. Sources are pulled locally by hand, and the pipeline never downloads.

## The channel model

The channel is the unit of curation.
One channel is one voice: one coherent recording family with its own placement (`min_distance`, `max_distance`, `height`) and its own cadence (`period0..3`).

- Pools are single-source by default: one pack's folder, files mastered together.
  Coherence is a verified property, never an inherited one.
  The packs' own folders are internally inconsistent, which is why the audibility pass exists.
  Every pool therefore passes a spread check (crest, spectral shape, noise floor) and the ear regardless of origin.
  Cross-pack pooling is a flagged exception, allowed only when measurement says the families are compatible and the ear confirms.
- Pool size: target 15-25 files (the ecosystem's own median-to-average band, measured across 7 packs), hard cap 40.
  A channel earns 26-40 only for a genuinely deep, uniform family.
  Past 40, overflow that forms a distinct character cluster becomes its own channel, and more-of-the-same is cut.
- The mechanical ceiling: one `sounds =` value is a single line read into a fixed 4096-byte buffer (`SoundRender_Core.cpp:249`).
  At the corpus average of 43 chars per token that is about 95 files. The `LINE_CAP = 3900` guard fails the build before the buffer can.
- Channels fill ROLES, and roles are a fixed menu per state class (clear day, clear night, rain, storm, fog, underground).
  The menu holds a bed, a wind, birds or their night counterpart, insects, foliage, a rare-treasure slot, and weather-specific extras.
  A new channel exists only by taking an empty role in some state or by beating the role's current holder.
  The scale lands in the spine's own neighbourhood (its 94 channels rationalized plus the gap additions), not in the hundreds.
- When one voice needs different cadence per state (common in storms, rare in clear weather), a twin definition carries the same pool with different periods.
  Twins are used sparingly, and the `fmt` guard keeps the twin lines identical.

## Density

Each state class has an ear-calibrated events-per-minute budget, and the budget is the conserved quantity.
The state's total emission rate (the sum of `1/mean(period2..3)` across its wired channels, weighted by sound length) never exceeds it.
A channel wired into a state is paid for in periods, its own or its neighbours'. A split channel repays in cadence, so a split can never raise the rate.

Three further rules keep many channels from becoming a wall:

- Entry burst: `period0..1` govern the first fire after a state change.
  A state's channels stagger their first-fire windows so a weather transition does not fire everything within 10 seconds.
- Distribution over stacking: a channel does not join every state its category appears in.
  Variety spreads across time and place (wind-howl in fog and night, wind-gust in day, the metal groan only in the deep underground presets), and concurrency per state stays flat.
- Rare-voice channels carry the treasures: periods of 120000-300000 ms put a one-in-a-hundred find in the world at almost no budget cost.

## Curation method

Division of labor:

- The curator (assistant) works from evidence: the measurement tables (LUFS, crest, duration, native channel count, rate), the source packs' own wiring, provenance, and the dedup maps.
  What channel the pack's author bound a file to is evidence. Ignoring it is how thunderclaps ended up in a wind channel.
  The curator drafts family-level A/B proposals, the channel vocabulary, and the wiring plans.
- The ear (the user) closes every contested call through the player (`ui_aa_player.script`): family vs family for a slot, the contested middle of a ranking, the density budgets per state class.
- The pipeline masters and proves. It never chooses.

Every excluded file or folder carries a written reason in the dispositions register (`tools/sources.py`). Nothing is deleted by inference.

## Audibility method

Community ambient corpora sound fine at-ear yet die in-game, for engine reasons (`doc/library/anomaly/internals/sound-source-and-emitter.md`):

1. A STEREO ogg force-plays 2D at-ear, escaping distance rolloff and occlusion. Only MONO spatialises.
2. Every 3D voice attenuates twice, through X-Ray's linear fade AND OpenAL's inverse model keyed on the ogg blob's `min_distance`.
   An unset min of 1-2 costs -26..-31 dB at a 25-50 m placement before the linear fade applies.
3. Content loudness is a separate floor the distance fixes cannot reach.

The mastering rules, scoped by playback path:

- Fold to mono (`fold`) applies to ALL 3D-played audio, ambient channels and strike files alike.
  The fold is the one lossy step. It captures the author blob first and resamples off-rate files to 44100, because the engine hard-rejects any other rate (`SoundRender_Source_loader.cpp:79`).
- The crest-inverted min-distance floor (`level`) applies to ambient channel files only.
  It floors each file's `min_distance` to a crest-keyed ratio (0.40-0.60) of its channel's felt-far placement, capped below `max_distance`, and never lowers an authored min.
  Strike files are excluded: the engine overrides their range per strike (see Thunder below), so blob distances do nothing there.
- The loudness band (`level`) is per-category, both arms lossless and partial.
  A floor lifts a file whose delivered loudness at its placement sits below the audible target, and a ceiling lowers a file above it. A file is only ever in one arm.
  Ambient targets come from the in-ear calibration ladder through the two-rolloff gain model. Strike files get their own target, calibrated to a nominal mid-distance strike.
- Placement: per-category spawn-distance caps in config hold each category's felt-far band.
- Dead audio (`dead`) is reported, not auto-deleted. A measured-dead file (content below -60 LUFS) leaves through the dispositions register.

All blob edits are lossless (audio pages byte-identical). The fold is the only re-encode, and it exists because the engine only positions mono.

## Thunder

Thunder has two homes, matching the engine's two systems:

1. Distant rumble: ambient channels in pre_storm/rain/storm states (`thunder_far`), curated and mastered like any voice.
2. Strike claps: the engine thunderbolt system.
   The weather mod (Atmospherics) drives timing per weather cycle (`thunderbolt_collection`, `thunderbolt_period`, `thunderbolt_duration` in `weathers/w_*.ltx`).
   The collections resolve to sections in `thunderbolts.ltx`, and each section's `sound =` names a path under `sounds\nature\`.
   AlifeAmbience deploys its curated strike recordings AT those vanilla paths (`DEPLOY_EXTRA` in `tools/sources.py`).
   The best claps play with zero config, and the weather mod's tuning stays intact.
   The engine plays each strike positioned at the bolt with a speed-of-sound delay and a per-strike attenuation range
   (`thunderbolt.cpp:235`: `snd.play_no_feedback(0, 0, dist / 300.f, &pos, 0, 0, &Fvector2().set(dist / 2, dist * 2.f))`).
   That is why strike files need selection and loudness only, and no placement engineering.

## Deduplication

Deduplication runs twice, both on our side, never against the target install. A byte hash collapses identical reships.
fpcalc (Chromaprint) fingerprints the deployed audio and reports same-recording aliases the byte hash cannot see. Short clips fall back to the byte hash.
In the authored-config model both run as warners. A duplicate pick is reported for the curator to resolve, never auto-repointed.

## The five-link binding chain

An ambient sound reaches the player through five links, and the verifier proves each resolves:

1. Weather state: the weather mod's `weathers/w_*.ltx` sets `ambient = <state>` per time frame.
   Atmospherics emits day, morning, evening, night, rain, rain_day, rain_night, storm_day, storm_night, tuman, tuman_night, and indoor_underground.
2. Level to preset: `ambients/<level>.ltx` is a one-line `#include` binding each map to a preset.
3. Preset to channels, per state: one section per weather state with `sound_channels` (the bed) and `sound_channels_dynamic` (the layers).
4. Channel to pool: `ambient_channels/backgrounds.ltx` and `sound_channels.ltx`.
5. Pool to ogg: the mastered audio files.

X-Ray lowercases section names on load (`strlwr(section)`, `Xr_ini.cpp:1613`), so references resolve case-insensitively.
The weather mod couples at exactly two vocabularies: the ambient state names (link 1) and the thunderbolt collection names (Thunder, home 2).
The links below those two are weather-mod-independent. Variants for other weather mods re-cover both vocabularies.

## Verification

`verify` emits the gate ledger, and the build fails unless every gate is clean:

1. No orphan file: every deployed ogg sits in some channel's pool or the strike deploy set.
2. No orphan channel: defined but unreferenced (informational, flagged as dead weight for the curator).
3. No dangling channel ref: every channel named in a preset is defined.
4. No missing sound path: every pool entry resolves to audio on disk.
5. Level routing closed: every map binds a preset, underground maps to underground presets.
6. Weather matrix full: every preset defines a section for every state the active weather mod emits.
7. Retention: every spine ambience-scope file and every file of an adopted folder is referenced or covered by a dispositions row.
   All other corpus content carries folder-level dispositions. Anything unaccounted is a FAIL.
8. Density: per state, the events-per-minute budget holds and the entry-burst stagger holds. The budget numbers arm the gate once the calibration sessions set them.
9. Line cap: no `sounds =` line approaches the 4096-byte ini buffer (`LINE_CAP = 3900`).
10. Collection coverage: every thunderbolt collection name the active weather mod references resolves in the base game's collection set.
11. Veto simulation: no channel that the AlifeSpooks veto touches may end EMPTY at load.
    The intersection itself is designed coexistence (the veto exists so base channels do not double the director's captured sounds).
    The veto generator appends `>sounds = ambient\no_sound` to every touched channel (AlifeSpooks `build.py:1065-1130`), so a fully-vetoed channel plays silence.
    A System A bed with no `sounds` key is a load failure (`Environment_misc.cpp:105-108`), which is exactly what that guard prevents.
    The gate FAILs only if a touched channel lacks the guard, and it reports fully-silenced channels as the Spooks-owned boundary picture.

## Coexistence with AlifeSpooks

AlifeSpooks captures the dark/horror content from the shared source packs into its own `zs/` tree.
It removes the captured paths with a generated static DLTX overlay: `mod_sound_channels_alifespooks.ltx`, individual `<sounds` removals per channel plus a `>sounds = ambient\no_sound` guard.
DLTX applies that overlay to OUR resolved `sound_channels.ltx`.
A captured path in one of our pools is stripped at load, a fully-captured channel plays silence, and gate 11 proves the composition stays safe.
The AlifeSpooks director places the horror, and the AlifeAmbience config plays the living ambience. Run both.

## The mastering mill

`tools/merge.py` reads the hand-written config as its input and does only what needs a machine:

- materialize: pull exactly the referenced files from the corpus packs into `gamedata/sounds`, and remove deployed files nothing references.
  The run is incremental. The audio-page-hash caches re-master only new files, and the working deployment is edited channel by channel, never wiped.
- master: `fold` and `level`, per the scoped rules above.
- stage / unstage: materialize a candidate family under `sounds/stage/` so the player can audition it in-game before it is picked.
- fmt: the mechanical guard for the config strings. It dedups pool tokens, normalizes preset lines, strips refs to deleted channels, caps spawn distances, and fails any pool line over the cap.
  Curation decides the sets, and `fmt` guards the strings.
- report: `fingerprint` (duplicate warnings) and `dead` (silent files), both for the curator.
- verify / audit: the gate ledger above, plus the wired min/felt-far and crushed-share acceptance report.

The generator stages of the earlier build (config synthesis, folder-dump grafts, spine path priority, prune-by-inference) are deleted.

## Invariants

- I1 Scope. Continuous nature/weather ambience and storm thunder. Horror one-shots are AlifeSpooks. Emission and psi-storm are their own systems. Strike timing belongs to the weather mod.
- I2 The config is authored. Machines master, report, and prove. They never choose content.
- I3 Spine completeness. Every ambience-scope file of the spine, across all its sound systems, is accounted for. Nothing dies silently.
- I4 One channel, one voice. Single-source pools by default, coherence verified, 15-25 target, 40 cap, roles-menu admission.
- I5 Density is conserved. The per-state budget and the entry-burst stagger are gates, not advice.
- I6 Audible by measurement. Mono fold, crest-inverted min floor, per-category loudness band, placement caps, scoped by playback path.
- I7 Preserve the source except where the engine forbids it. Blob-only edits, audio pages byte-identical, the fold as the one re-encode.
- I8 Deduplicate twice, warn, let the curator resolve.
- I9 Config closed. The full gate set passes or the build fails.
- I10 Weather-mod-bound at exactly two vocabularies (ambient states, collection names).
- I11 Traceable and licensed. Every deployed sound resolves to its origin, the licence gate clears every source, and the readme credits every author.

## Scripts: dependency gate, MCM, diagnostics, player (no gameplay)

- `_aa_deps.script` holds the version constant, the xlibs + modded-exes floor asserts, the platform line, and the boot banner.
- `aa_mcm.script` is the informational MCM. There is no master volume slider: the build levels loudness into the blob, and the game's ambient slider sets the overall level.
- `aa_debug.script` holds the xlog logger and the level gate.
- `aa_diag.script` is the runtime wiring inspector: active level, weather, ambient state, per-state channel counts, and a live dangling-ref count.
- `ui_aa_player.script` is the curation instrument, mirroring the AlifeSpooks player's shape.
  It is a keyboard-owning modal on PageUp (AlifeSpooks keeps PageDown), gated by the MCM sound_player toggle.
  It browses BY CHANNEL from the resolved `sound_channels.ltx` and auditions as-wired at the channel's real placement, at-ear, and at fixed distances.
  It steps within pools and staged candidate families for A/B rulings.
  Ear verdicts go to `alifeambience_notes.txt`, an investigation log that nothing parses.
  It is an own copy by family precedent, and it moves to xlibs only when a third consumer exists.

## Deploy

A gamedata overlay. The repo holds the authored config, the mastered audio, the mill, and the docs. Wiring for local sync goes through `stalker-manager`.
Every source carries a free licence or the author's permission before public release (see `licensing.md`), and the readme credits each author.
