# AlifeAmbience: the most complete and most refined ambient soundscape for STALKER Anomaly

Every sound measured, curated, and engineered instead of crammed together. The build chooses content best-of-breed per category from the strongest soundscape packs and deduplicates by waveform,
then makes it actually sound in the Zone: folded to mono so everything positions in 3D, distance-corrected so each sound carries and decays naturally across its area,
and loudness-banded to an ear-calibrated target so nothing turns muffled or blaring. Birds, insects, wind, frogs, crows, foliage, rain, the helicopter, and the day/night ecosystem,
wired to the weather so the Zone breathes.

It is the bed counterpart to [AlifeSpooks](https://github.com/damiansirbu-stalker/AlifeSpooks). AlifeSpooks owns the horror one-shots and vetoes them out of the base channels.
AlifeAmbience owns the audible living bed AlifeSpooks leaves alone. Run both for realism and horror at once.

Requires: Anomaly 1.5.3, a DLTX-capable engine (the modded exes / GAMMA), and a weather mod whose ambient states the bed covers (Atmospherics out of the box).

## What makes it different

- Best-of-breed, not a pile. Each category (wind, weather, birds, insects, frogs, foliage, helicopter) comes from the pack that measured best for it, not one pack taken whole.
  The build culls dead, muffled, and redundant audio rather than keeping it.
- Actually audible. The engine crushes most community ambience to a whisper at range and cannot position stereo at all. AlifeAmbience folds every file to mono,
  floors each file's distance reference so it carries, and levels loudness into an ear-calibrated band, all as lossless edits to the sound's own metadata.
- Scientific, not guessed. It profiles every file for loudness (LUFS) and transient shape (crest), verifies the playback gain against the X-Ray engine's own attenuation math,
  and takes the targets from a listening calibration.
- Proven complete. A config-closure check gates every build: no map goes silent, no weather state goes silent, no reference dangles.

## How it is built

A reproducible pipeline (`tools/merge.py`) selects the roster, deduplicates by waveform, folds stereo to mono, floors each file's min-distance (crest-inverted,
so a sustained tone carries and a transient stays near-field), levels loudness into a floor-and-ceiling band, culls the dead, and reconciles the level and weather config into one closed set.
A closure verifier and an audibility audit gate every build. See [architecture.md](doc/architecture.md).

## Alife Collection

- [AlifeBalance](https://www.moddb.com/mods/stalker-anomaly/addons/alifebalance)
- [AlifeDiegetic](https://www.moddb.com/mods/stalker-anomaly/addons/diegetic-audio-control-100)
- [AlifeGuard](https://www.moddb.com/mods/stalker-anomaly/addons/alifeguard-1001)
- [AlifePlus](https://www.moddb.com/mods/stalker-anomaly/addons/alifeplus-v1-0-01)
- [AlifeSpooks](https://github.com/damiansirbu-stalker/AlifeSpooks)
- [AlifeTactics](https://www.moddb.com/mods/stalker-anomaly/addons/alifetactics)

## Documentation

- [readme.txt](doc/readme.txt): full description, what it adds, credits
- [architecture.md](doc/architecture.md): method, invariants, build pipeline
- [licensing.md](doc/licensing.md): every source's license and the granting author's permission

## License

PolyForm Perimeter License. See [LICENSE](LICENSE).
