AlifeAmbience: a living nature-and-weather ambient bed for STALKER Anomaly, by Damian
Version: next
GitHub: https://github.com/damiansirbu-stalker/AlifeAmbience
Changelog: https://github.com/damiansirbu-stalker/AlifeAmbience/blob/main/doc/changelog
Bugs, suggestions: https://github.com/damiansirbu-stalker/AlifeAmbience/issues

Alife Collection:
AlifeBalance: https://www.moddb.com/mods/stalker-anomaly/addons/alifebalance
AlifeDiegetic: https://www.moddb.com/mods/stalker-anomaly/addons/diegetic-audio-control-100
AlifeGuard: https://www.moddb.com/mods/stalker-anomaly/addons/alifeguard-1001
AlifePlus: https://www.moddb.com/mods/stalker-anomaly/addons/alifeplus-v1-0-01
AlifeSpooks: https://github.com/damiansirbu-stalker/AlifeSpooks
AlifeTactics: https://www.moddb.com/mods/stalker-anomaly/addons/alifetactics

Modern soundscape mods carry rich ambience but ship it near-silent: the calm-day air of the stock
packs measures dead, so the Zone sounds empty in fair weather. AlifeAmbience fixes that. It merges the
best beds from several packs into one living nature-and-weather bed and levels every file to one even,
audible loudness, so birds, insects, wind, frogs, crows, and weather actually sound.

It is the bed companion to AlifeSpooks. AlifeSpooks plays the horror one-shots and removes them from the
base channels; AlifeAmbience owns the audible living bed AlifeSpooks leaves alone. Run both and the Zone
is real and frightening at once.

What it does
No single pack has everything. One pack has the audible bed masters but thin content, another the
richest species (frogs, night birds, time-of-day insects) but dead loudness, another the widest map and
weather config. AlifeAmbience merges them: the audible masters, the rich species, the full map and
weather config, deduplicated by exact waveform and re-leveled to one target loudness. The result is a
day/night ecosystem, audible, that no shipped pack is.

Wired to the weather. Every map and every weather state your weather mod emits resolves to a bed. A
config-closure check proves it before any build ships: no map goes silent, no weather goes silent, no
sound reference dangles. Built and verified against Atmospherics out of the box.

How the loudness works. Each bed's average loudness is measured and leveled to one common target by
setting its X-Ray gain field in the ogg comment, capped so no peak clips and floored so nothing goes
silent. It is a number in the header, not the audio, so the whole bed plays at one even level with no
re-encode.

Requirements:
Anomaly 1.5.3
A DLTX-capable engine (the modded exes / GAMMA)
A weather mod whose ambient states the bed covers (Atmospherics out of the box)
MCM (for the master volume balance)

Install (MO2):
1. Install this mod
2. Load it so its ambient config wins (below other soundscape beds you are replacing)
3. Configure the master volume via MCM

Uninstall (MO2):
Disable or remove in MO2. Weather visuals are your weather mod's job and are untouched.

Compatibility:
Built for GAMMA with Atmospherics, and it runs on vanilla Anomaly and any weather mod whose ambient
states the bed covers. It is a bed layer: it wins the ambient sound config and plays the merged bed. It
composes with AlifeSpooks, which places horror one-shots and vetoes its own sounds out of the base
channels, so the living bed and the horror never double. It does not touch weather visuals, emission,
or psi-storm.

Credits:
The bed is merged from community soundscape packs, with thanks to their authors: the Dark Signal family
and Amplified Soundscape by Shrike, including unreleased interior audio he made and never released;
RETUNE by Aphrodite_child; Audio Expansion by AniHVX; Immersive Ambience Expansion by Kutee; Soundscape
Overhaul by Solarint. Base beds come from the original S.T.A.L.K.E.R. games.
Every author is credited above. Only selected audio is redistributed. If an author does not want their
work included, it is removed from the build.
Each source's license and the granting author's permission are recorded in licensing.md; nothing ships
without a free license or the author's consent.

Usage and License:
Modpacks are allowed and encouraged. Keep the readme and license files.
Addons, patches, and integrations are allowed. Credit "AlifeAmbience by Damian Sirbu" visibly on your
mod page.
You may not reproduce the implementation in other software, even with credit.
The full license is in the LICENSE file and on GitHub.

Issues and suggestions:
Open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the
GAMMA, EFP, Anomaly, and Zona Discord servers.
Read this readme first.
