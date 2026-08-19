# AlifeAmbience: a living nature-and-weather ambient bed for STALKER Anomaly

Merges the best ambient beds from several soundscape packs into one audible, per-map, per-weather nature bed: birds, insects, wind, frogs, crows, foliage, rain, and the day/night ecosystem, leveled to one even loudness and wired to the weather so the Zone breathes.

It is the bed counterpart to [AlifeSpooks](https://github.com/damiansirbu-stalker/AlifeSpooks): AlifeSpooks owns the horror one-shots and vetoes them out of the base channels; AlifeAmbience owns the audible living bed AlifeSpooks leaves alone. Run both for realism and horror at once.

Requires: Anomaly 1.5.3, a DLTX-capable engine (the modded exes / GAMMA), and a weather mod whose ambient states the bed covers (Atmospherics out of the box).

## What it does

- A curated, deduplicated nature/weather bed built from the audible masters and the richest content across the source packs, not one pack picked whole.
- Every bed leveled to one even loudness (the "dead calm-day air" of the stock packs is fixed), so the ambience is actually audible.
- Wired to the weather engine: every map and every weather state the weather mod emits resolves to a bed, proven by a config-closure ledger, so no weather goes silent.

## How it is built

A pipeline (`tools/`) merges each pack's beds, dedups by exact content, re-levels every file's loudness losslessly (the X-Ray gain field in the ogg comment, the same masterization AlifeSpooks uses), and reconciles the level + weather config into one closed set. A verifier proves the config closure before any build ships. See [architecture.md](doc/architecture.md).

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
