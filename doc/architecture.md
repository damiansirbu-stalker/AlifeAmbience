# AlifeAmbience - architecture and method

AlifeAmbience is the atmosphere soundscape for S.T.A.L.K.E.R. Anomaly: every map, every weather state, every hour plays a living, audible, varied ambience.
It is a curated work. The config is the source of truth, authored by hand: the channels, their pools, the presets, the level bindings.
The pipeline (`tools/merge.py`) is a mastering mill. It materializes, masters, reports, and proves what the config says. It never chooses content.

The soundscape carries its own dread layer: distant mutant cries, far gunfire, spooks and dark ambience play standalone.
AlifeSpooks is optional on top. Its director places dynamic horror one-shots, and its static veto takes the captured sounds out of the base channels at load, so the two never double.

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
The licence field is provenance record only, and `doc/licensing.md` holds the basis per source. Sources are pulled locally by hand, and the pipeline never downloads.

## The channel model

The channel is the unit of curation.
One channel is one voice: one coherent recording family with its own placement (`min_distance`, `max_distance`, `height`) and its own cadence (`period0..3`).

- Pools are single-source by default: one pack's folder, files mastered together.
  Coherence is a verified property, established per pool.
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

1. Distant rumble: ambient channels in the rain/storm states (`thunder_far`), curated and mastered like any voice.
   The `pre_storm` sections carry it too, but no stock or Atmospherics keyframe emits that state (see The five-link binding chain).
2. Strike claps: the engine thunderbolt system.
   The weather mod (Atmospherics) drives timing per weather cycle (`thunderbolt_collection`, `thunderbolt_period`, `thunderbolt_duration` in `weathers/w_*.ltx`).
   The collections resolve to sections in `thunderbolts.ltx`, and each section's `sound =` names a path under `sounds\nature\`.
   AlifeAmbience deploys its curated strike recordings AT those vanilla paths (`DEPLOY_EXTRA` in `tools/sources.py`).
   The best claps play with zero config, and the weather mod's tuning stays intact.
   The engine plays each strike positioned at the bolt with a speed-of-sound delay and a per-strike attenuation range
   (`thunderbolt.cpp:235`: `snd.play_no_feedback(0, 0, dist / 300.f, &pos, 0, 0, &Fvector2().set(dist / 2, dist * 2.f))`).
   That is why strike files need selection and loudness only, and no placement engineering.

## The effect layer

System A carries a second output besides the bed: ambient EFFECTS, a particle burst plus a wind blast plus one recording, fired outdoors on the preset's `min/max_effect_period` timer.
`CEnvAmbient::load` reads the `effects =` key, and the play block in `CGamePersistent::WeathersUpdate` is gated on outdoor luminocity.
Vanilla wires `effect_0..9` into every outdoor state: fog wisps and gust particles with the trx `wind_gust` recordings.

The layer is dead across the AtmosFear-lineage packs (found 2026-09-03).
The Dark Signal configs strip the `effects` keys from every preset, and Atmospherics' `effects.ltx` re-points all ten sounds at `nature\wind_01..10`, files that exist in no db archive and no mod.
Where the keys survive (the 304 field preset), the sounds play as silence.

AlifeAmbience restores both halves.
Every outdoor state of every preset wires `effect_0..9`.
The DLTX overlay `mod_effects_alifeambience.ltx` points the ten `sound =` keys at vanilla's proven trx recordings, winning over whichever `effects.ltx` is active.
Those recordings are the same class of repair as the surge beds.
Their only source is vanilla, which the channel resolver skips, and no channel reads the override.
So `DEPLOY_EXTRA` rows (`tools/sources.py`) carry the nine `ambient\trx\nature\wind_gust` files the override names.
Underground presets keep empty `effects` (the play block never fires indoors, vanilla parity).

The surge beds are the same class of repair.
`blowout_channels.ltx` inherited `blowout_impacts`, `blowout_rumble`, `blowout_ambient` and `blowout_flare` muted, because their only source is vanilla itself, which the resolver skips.
Explicit `DEPLOY_EXTRA` rows (`tools/sources.py`) now pull the 21 vanilla `ambient\trx\blowout` recordings and the four pools play again during emissions.

## Deduplication

Deduplication runs twice, both on our side, never against the target install. A byte hash collapses identical reships.
fpcalc (Chromaprint) fingerprints the deployed audio and reports same-recording aliases the byte hash cannot see. Short clips fall back to the byte hash.
In the authored-config model both run as warners. A duplicate pick is reported for the curator to resolve by hand.

## The five-link binding chain

An ambient sound reaches the player through five links, and the verifier proves each resolves:

1. Weather state: the active weather set's `weathers/w_*.ltx` sets `ambient = <state>` per time frame.
   The vocabulary is the AtmosFear set: day, morning, evening, night, rain, rain_day, rain_night, storm_day, storm_night, tuman, tuman_night, and indoor_underground.
   Stock Anomaly 1.5.3 and Atmospherics emit exactly this set (both weather trees swept 2026-09-03), so the mod runs on either with no variant.
   The presets also carry `pre_storm` and `tuman_day` sections, the vanilla preset shape. No stock or Atmospherics keyframe emits them, so they stay inert until a weather mod uses those states.
   Weather mechanics of record: `stalker-dev/doc/library/anomaly/internals/weather-system.md`.
2. Level to preset: `ambients/<level>.ltx` is a one-line `#include` binding each map to a preset.
3. Preset to channels, per state: one section per weather state with `sound_channels` (the bed) and `sound_channels_dynamic` (the layers).
4. Channel to pool: `ambient_channels/backgrounds.ltx` and `sound_channels.ltx`.
5. Pool to ogg: the mastered audio files.

X-Ray lowercases section names on load (`strlwr(section)`, `Xr_ini.cpp:1613`), so references resolve case-insensitively.
The weather layer couples at exactly three vocabularies: the ambient state names (link 1), the thunderbolt collection names (Thunder, home 2), and the effect ids (The effect layer).
The links below those three are weather-mod-independent. Variants for other weather mods re-cover all three vocabularies.

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
8. Density: per state, the events-per-minute budget holds and the entry-burst stagger holds. Armed 2026-09-09 with per-state-class DENSITY_BUDGET (merge.py) as loud regression ceilings, a guard against a future blowout, not the tight ear-calibrated budget. The epm sum uses the round-robin cap (60000/mean(period0..3), one channel per tick) but still counts no_sound channels, a known over-count the loose ceilings tolerate; tighten only after the sum excludes silent channels and the ear calibrates real values.
9. Line cap: no `sounds =` line approaches the 4096-byte ini buffer (`LINE_CAP = 3900`).
10. Collection coverage: every thunderbolt collection name the active weather mod references resolves in the base game's collection set.
11. Veto simulation: no channel that the AlifeSpooks veto touches may end EMPTY at load.
    The intersection itself is designed coexistence (the veto exists so base channels do not double the director's captured sounds).
    The veto generator appends `>sounds = ambient\no_sound` to every touched channel (AlifeSpooks `build.py:1065-1130`), so a fully-vetoed channel plays silence.
    A System A bed with no `sounds` key is a load failure (`Environment_misc.cpp:105-108`), which is exactly what that guard prevents.
    The gate FAILs only if a touched channel lacks the guard, and it reports fully-silenced channels as the Spooks-owned boundary picture.
12. Level coverage: every playable base-game level (`LEVELS_BASE`, the `game_maps_single.ltx` set minus `fake_start`) binds an `ambients/<level>.ltx`.
    An unbound level plays vanilla wiring through the MO2 VFS (the 9 labs, found 2026-09-03) or a bare `ambients.ltx` fallback with zero dynamic layers (`y04_pole`).
    Bindings outside the base set (extended maps) are reported, not failed.
13. Bed load asserts: every channel any preset or `ambients.ltx` names as a bed satisfies `SSndChannel::load` (`Environment_misc.cpp:88-108`):
    `max_distance > min_distance` strict, `period0 <= period1`, `period2 <= period3`, non-empty `sounds`. A violation is a CTD on level load.
14. Dynamic completeness: every channel named in any `sound_channels_dynamic` defines all 4 periods and both distances, or `sound_ambient.script` nil-errors and breaks that hour's rotation.
15. Indoor routing: no `indoor = true` channel is wired into an outdoor state, where the System B volume table (`sound_ambient.script:147-165`) plays it at 0.0.
    Outdoor channels inside underground states (played at 0.3) are reported, not failed.
16. Strike palette (informational): of the bolt sounds reachable through the collections the weathers reference, how many carry our deploy vs vanilla audio.
17. Effect vocabulary: every effect id any preset or `ambients.ltx` wires exists in the base effect set (`effect_0..9` + `blowout_effect_01..48`).
    An unknown id is a CTD: `create_effect` reads `life_time` with a throwing `r_float` (`Environment_misc.cpp:119-146`).
18. Effect sound paths: every `sound =` in the effect override resolves to a file on disk.
    No channel reads the override, so gate 4 never sees these paths. A dangling one plays silent, since `WeathersUpdate` skips a null handle, with no other trace.

## Coexistence with AlifeSpooks

AlifeSpooks captures the dark/horror content from the shared source packs into its own `zs/` tree.
It removes the captured paths with a generated static DLTX overlay: `mod_sound_channels_alifespooks.ltx`, individual `<sounds` removals per channel plus a `>sounds = ambient\no_sound` guard.
DLTX applies that overlay to OUR resolved `sound_channels.ltx`.
A captured path in one of our pools is stripped at load, a fully-captured channel plays silence, and gate 11 proves the composition stays safe.
The AlifeSpooks director places the horror, and the AlifeAmbience config plays the living ambience.
Standalone, nothing is vetoed and the full dread layer plays. With AlifeSpooks installed, the directed layer replaces the captured subset.

## The mastering mill

`tools/merge.py` reads the hand-written config as its input and does only what needs a machine:

- materialize: pull exactly the referenced files from the corpus packs into `gamedata/sounds`, and remove deployed files nothing references.
  The run is incremental. The audio-page-hash caches re-master only new files, and the working deployment is edited channel by channel, never wiped.
- master: `fold` and `level`, per the scoped rules above.
- stage / unstage: materialize a candidate family under `sounds/stage/` so the player can audition it in-game before it is picked.
- import: the one-time config baseline from a source pack's own sound-routing config (default: the Amplified spine), the bootstrap for a fresh variant.
  It is a mechanical copy of the pack author's wiring, excluded from `all`, and it refuses over an existing config so it cannot overwrite curation.
- fmt: the mechanical guard for the config strings. It dedups pool tokens, normalizes preset lines, strips refs to deleted channels, caps spawn distances, and fails any pool line over the cap.
  Curation decides the sets, and `fmt` guards the strings.
- report: `fingerprint` (duplicate warnings) and `dead` (silent files), both for the curator.
- verify / audit: the gate ledger above, plus the wired min/felt-far and crushed-share acceptance report.

The generator stages of the earlier build (config synthesis, folder-dump grafts, spine path priority, prune-by-inference) are deleted.

## Invariants

- I1 Scope. Nature/weather ambience, the ambient dread layer, storm thunder. Directed one-shots are AlifeSpooks. Emission and psi-storm are their own systems. Strike timing is the weather mod's.
- I2 The config is authored. Machines master, report, and prove. They never choose content.
- I3 Spine completeness. Every ambience-scope file of the spine, across all its sound systems, is accounted for. Nothing dies silently.
- I4 One channel, one voice. Single-source pools by default, coherence verified, 15-25 target, 40 cap, roles-menu admission.
- I5 Density is conserved. The per-state budget and the entry-burst stagger are gates, not advice.
- I6 Audible by measurement. Mono fold, crest-inverted min floor, per-category loudness band, placement caps, scoped by playback path.
- I7 Preserve the source except where the engine forbids it. Blob-only edits, audio pages byte-identical, the fold as the one re-encode.
- I8 Deduplicate twice, warn, let the curator resolve.
- I9 Config closed. The full gate set passes or the build fails.
- I10 Weather-mod-bound at three vocabularies (ambient states, collection names, effect ids). Stock Anomaly and Atmospherics share all three. Other weather mods need a sweep of all three first.
- I11 Traceable and licensed. Every deployed sound resolves to its origin, `licensing.md` records the basis for every source, and the readme credits every author.
- I12 No audible sound is dropped before the user auditions it. Measurement only FLAGS a drop candidate (too long, off-character, past a spectral or loudness bound); it never excludes an audible file on its own. The flagged list is loaded into `ui_aa_player` as a playlist, the user auditions it, and only then does a file get a DISPOSITIONS `excluded` row. The sole mechanical removals are files that cannot be auditioned: dead-silent (below the LUFS floor), off sample rate, corrupt, or an anti-phase pair that folds to silence. This invariant is shared verbatim with AlifeSpooks.

## Scripts: dependency gate, MCM, diagnostics, player (no gameplay)

- `_aa_deps.script` holds the version constant, the xlibs + modded-exes floor asserts, the platform line, and the boot banner.
- `aa_mcm.script` is the informational MCM. There is no master volume slider: the build levels loudness into the blob, and the game's ambient slider sets the overall level.
- `aa_debug.script` holds the xlog logger and the level gate.
- `aa_diag.script` is the runtime wiring inspector (active level, weather, ambient state, per-state channel counts, live dangling-ref count) AND the runtime sound trace. The trace subscribes through the xlibs seam registry to the 6 demonized sound callbacks (bed, script-sound, effect, thunderbolt, rain, level-music) and logs each fire with its resolved channel and file, gated on `aa_debug.is_on()`. It is a no-op on a stock exe (the seam returns false and never attaches) and observe-only (returns nil, never a veto). This is the runtime counterpart to the static wiring dump, and the ground truth for the density and repetition rulings.
- `ui_aa_player.script` is the curation instrument, mirroring the AlifeSpooks player's shape.
  It is a keyboard-owning modal on PageUp (AlifeSpooks keeps PageDown), gated by the MCM sound_player toggle.
  It browses BY CHANNEL from the resolved `sound_channels.ltx` and auditions as-wired at the channel's real placement, at-ear, and at fixed distances.
  It steps within pools and staged candidate families for A/B rulings.
  Ear verdicts go to `alifeambience_notes.txt`, an investigation log that nothing parses.
  It is an own copy by family precedent, and it moves to xlibs only when a third consumer exists.

## Deploy

A gamedata overlay. The repo holds the authored config, the mastered audio, the mill, and the docs. Wiring for local sync goes through `stalker-manager`.
Every source carries a free licence or the author's permission before public release (see `licensing.md`), and the readme credits each author.
