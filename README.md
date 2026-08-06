# AlifeSpooks: a dark-mood ambient overlay for STALKER Anomaly

Gathers the dreadful, horror, and mournful sounds from several soundscape packs, keeps the best-quality copy of each, and layers them over your existing ambience: mutant growls, distant screams, underground dread, ominous drones, creeping wind, eerie animals, and oppressive weather.
It overrides no ambient files, composing through DLTX, so it layers onto GAMMA, vanilla, or any other soundscape.

[ModDB](TBD) | [Releases](https://github.com/damiansirbu-stalker/AlifeSpooks/releases) | [Bugs, suggestions](https://github.com/damiansirbu-stalker/AlifeSpooks/issues)

Requires: Anomaly 1.5.3, a DLTX-capable engine (the modded exes / GAMMA). xlibs is optional: it adds the MCM and the in-game trace; without it the content runs on its own.

## What it adds

Over your base ambience, switched on per map and time:

- Dread: distant mutant growls, far-off screams, spooks, dark ambience, the dark-signal cue.
- Underground: the full tunnel and lab set - whispers, rats, banging, metal groans, drips.
- Tension: distant gunfire, ominous drones, creeping wind, branch creaks.
- Eerie atmosphere: owls, distant dogs, crows, fog.
- Oppressive weather: storms, rain, howling wind.

It leaves generic daytime life (birdsong, insects, plain wind) to your base ambience, and does not touch emission or psi-storm sound.

## How it is built

A pipeline (`tools/`) merges each pack's channels by their own curation, keeps the dark set, dedups by exact content, picks the softest and rarest settings any pack uses, harmonizes how many layers play at once, and emits a DLTX overlay. See [architecture.md](doc/architecture.md).

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
- [changelog](doc/changelog): version history

## License

PolyForm Perimeter License. See [LICENSE](LICENSE).
