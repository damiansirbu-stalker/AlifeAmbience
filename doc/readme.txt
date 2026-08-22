AlifeAmbience: the most complete and most refined ambient soundscape for STALKER Anomaly, by Damian
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

The ambience of the Zone is some of the finest atmosphere in gaming, but in Anomaly you barely hear it. It is scattered across a dozen soundscape packs, most files fade to near-silence a few metres
from where they play, and half are stereo, which the engine cannot place in the world at all, so the Zone sounds empty in fair weather.
AlifeAmbience takes the best of the finest community soundscape packs, combines and mixes them tastefully into one living nature-and-weather soundscape,
then engineers every sound by measurement: proper 3D positioning, distance and decay tuned to each sound's character, and loudness leveled to a calibrated target.
It is the most complete and most refined ambient soundscape for Anomaly.

It is the ambient companion to AlifeSpooks. AlifeSpooks plays the horror one-shots and removes them from the base channels. AlifeAmbience owns the audible living ambience AlifeSpooks leaves alone.
Run both and the Zone is real and frightening at once.

Overview
No single pack has everything, and no pack is audible out of the box. AlifeAmbience takes the best source for each part of the soundscape (environment ambience, insects and frogs, wind, the helicopter,
birds, foliage, weather), deduplicates them by waveform, and then engineers the result so it actually sounds in the world: every file folded to mono so the engine can position it in 3D,
every file's distance range corrected so it carries and decays across its area instead of vanishing, and loudness leveled into a calibrated band so nothing turns muffled or blaring.
The build removes dead, muffled, and redundant audio rather than keeping it. The result is a day/night ecosystem, audible at placement, that no single pack is.

Measurement
The choices come from measurement, not taste. It profiles every file for loudness and transient shape with broadcast tools (ffmpeg's ebur128 and astats),
computes its delivered volume against the X-Ray engine's own attenuation math, and takes the targets, how present each kind of sound should be and how it decays with distance,
from an in-ear calibration. Identity is the waveform, checked by hash, so no recording enters the build twice.

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
A DLTX-capable engine (the modded exes / GAMMA)
A weather mod whose ambient states the soundscape covers (Atmospherics out of the box)
MCM (optional, for the version footer and diagnostics)

Install (MO2):
1. Install this mod
2. Load it so its ambient config wins (below other soundscape mods you are replacing)
3. Adjust ambient loudness with the game's own sound options if needed

Uninstall (MO2):
Disable or remove in MO2. Weather visuals are your weather mod's job and are untouched.

Compatibility:
Runs on Anomaly and any weather mod whose ambient states the soundscape covers, Atmospherics included. It is the ambient layer: it wins the ambient sound config and plays the merged soundscape.
It composes with AlifeSpooks, which places horror one-shots and vetoes its own sounds out of the base channels, so the living ambience and the horror never double. It does not touch weather visuals,
emission, or psi-storm.

Credits and permission:
AlifeAmbience draws from community soundscape packs, with thanks to their authors: Dark Signal Amplified Soundscape by Shrike, Audio Expansion by AniHVX, Immersive Ambience Expansion by Kutee,
and Soundscape Overhaul by Solarint. Each pack carries the author's permission or its own free license. licensing.md records the basis per addon.

Usage and License:
Modpacks are allowed and encouraged. Keep the readme and license files. Addons, patches, and integrations are allowed. Credit "AlifeAmbience by Damian Sirbu" visibly on your mod page.
You may not reproduce the implementation in other software, even with credit. The full license is in the LICENSE file and on GitHub.

Issues and suggestions:
Open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the
GAMMA, EFP, Anomaly, and Zona Discord servers.
Read this readme first.
