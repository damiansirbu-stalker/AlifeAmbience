AlifeAmbience: a curated, audible ambient soundscape for STALKER Anomaly, by Damian
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

The Zone's ambience is a huge part of what makes STALKER, but in Anomaly you barely hear it. It is scattered across a dozen soundscape packs, most files fade to near-silence a few metres
from where they play, and half are stereo, which the engine cannot place in the world at all, so the Zone sounds empty in fair weather.
AlifeAmbience draws on that whole lineage, from the original games through the classic overhaul mods (Solyanka/NS OGSR, OGSE, Dead Air, Lost Alpha)
to the community soundscape packs that carry it forward, and combines the best of it into one living nature-and-weather soundscape, engineered by measurement to sound right in the world.

It is the ambient companion to AlifeSpooks. AlifeSpooks plays the horror one-shots and removes them from the base channels. AlifeAmbience owns the audible living ambience AlifeSpooks leaves alone.
Run both and the Zone is real and frightening at once.

Overview
No single pack has everything, and no pack is audible out of the box. AlifeAmbience takes the best source for each part of the soundscape: environment ambience, insects and frogs, wind, the helicopter,
birds, foliage, and weather. It removes dead, muffled, and redundant audio rather than keeping it.
The result is a day/night ecosystem, audible at placement, that no single pack is.

Measurement
Every choice comes from measurement, not taste. ffmpeg's ebur128 reads each file's loudness as broadcast LUFS, and astats reads its shape, a steady bed versus a sharp transient, from the crest factor and true peak.
Those numbers feed a reconstruction of the engine's own two-stage attenuation, so the loudness the build aims for is what you hear at the sound's placement, not a figure on disk.
The per-category targets, how present each kind of sound is and how far it carries, come from an in-ear calibration.
A content hash removes byte-identical copies. An acoustic fingerprint (Chromaprint) then removes the same recording re-encoded or renamed under another name, so a sound never plays twice from two files.

Weather coverage
Every map and every weather state your weather mod emits resolves to an ambient set. A config-closure check proves it before release: no map goes silent, no weather goes silent,
no sound reference dangles. It targets Atmospherics out of the box and verifies against it.

Audibility
The engine fades a sound with distance from a reference set in each file, and almost every community file leaves that reference at the tool default, which fades to a whisper within a few metres.
AlifeAmbience raises each file's reference to match where its channel places it, keyed to the sound's character (a sustained tone carries, a sharp transient stays near),
so it decays naturally instead of vanishing. Stereo files, which the engine plays flat at your ears with no direction, fold to mono so they position in the world.
The build levels loudness into a band, lifting quiet content and easing hot content, to a calibrated target, as a lossless edit to each file's own data.
The game's ambient volume slider still sets the overall level on top.

Requirements:
Anomaly 1.5.3
A DLTX-capable engine (the modded exes: themrdemonized or AOEngine)
A weather mod whose ambient states the soundscape covers (Atmospherics out of the box)
MCM (optional, for the version footer and diagnostics)

Install (MO2):
1. Install xlibs
2. Install AlifeAmbience
3. Give it higher MO2 priority than any other ambient or soundscape mod, so its config wins
4. Keep a weather mod active whose ambient states AlifeAmbience covers. Atmospherics is the reference it is built and verified against, and covers every map and state out of the box
5. Optional: MCM for the version footer and diagnostics. The game's own sound options set overall ambient loudness

GAMMA players (the xlibs + Alife stack): GAMMA already ships Atmospherics, so the weather side is covered. Disable the soundscape mods AlifeAmbience replaces, so nothing leaks through:
304- Dark Signal Weather and Ambiance Audio, 3- Soundscape Overhaul, G.A.M.M.A. Soundscape Overhaul, and G.A.M.M.A. Dark Signal Audio Lite. Run AlifeSpooks alongside for the horror layer.

Uninstall (MO2):
Disable or remove in MO2. Weather visuals are your weather mod's job and are untouched.

Compatibility:
Runs on Anomaly and any weather mod whose ambient states the soundscape covers, Atmospherics included. It is the ambient layer: it wins the ambient sound config and plays the merged soundscape.
It composes with AlifeSpooks, which places horror one-shots and vetoes its own sounds out of the base channels, so the living ambience and the horror never double. It does not touch weather visuals,
emission, or psi-storm.
Tested with Anomaly 1.5.3 and GAMMA. Install or uninstall anytime; it is config and sounds, with no save state.

Credits and permission:
AlifeAmbience draws from community soundscape packs, with thanks to their authors: Dark Signal Amplified Soundscape by Shrike, Audio Expansion by AniHVX, Immersive Ambience Expansion by Kutee,
and Soundscape Overhaul by Solarint. Each pack carries the author's permission or its own free license. licensing.md records the basis per addon.

Usage and License:
Modpacks are allowed and encouraged. Keep the readme and license files. Addons, patches, and integrations are allowed. Credit "AlifeAmbience by Damian Sirbu" visibly on your mod page.
You may not reproduce the implementation in other software, even with credit. The full license is in the LICENSE file and on GitHub.

Issues and suggestions:
Open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the
EFP, Anomaly, and Zona Discord servers.
Read this readme first.
