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

Modern soundscape packs carry rich ambience, but in-game you barely hear it: most files fade to near-silence a few metres from where they play, and half of them are stereo,
which the engine cannot place in the world at all. So the Zone sounds empty in fair weather. AlifeAmbience fixes that, and does it with care rather than by piling packs on top of each other.
It is the most complete and most refined ambient soundscape for Anomaly: every sound measured, curated, and engineered instead of crammed together.

It is the bed companion to AlifeSpooks. AlifeSpooks plays the horror one-shots and removes them from the base channels; AlifeAmbience owns the audible living bed AlifeSpooks leaves alone.
Run both and the Zone is real and frightening at once.

What it does
No single pack has everything, and no pack is audible out of the box. AlifeAmbience takes the best source for each part of the soundscape (environment beds, insects and frogs, wind, the helicopter,
birds, foliage, weather), deduplicates them by waveform, and then engineers the result so it actually sounds in the world: every file folded to mono so the engine can position it in 3D,
every file's distance range corrected so it carries and decays across its area instead of vanishing, and loudness leveled into a calibrated band so nothing is muffled or blaring. Dead, muffled,
and redundant audio is removed, not kept. The result is a day/night ecosystem, audible at placement, that no single pack is.

Measured, not guessed
The choices are made by measurement, not taste. Every file is profiled for loudness and transient shape with broadcast tools (ffmpeg's ebur128 and astats),
its delivered volume is computed against the X-Ray engine's own attenuation math, and the targets, how present each kind of sound should be and how it decays with distance,
come from an in-ear calibration. Identity is the waveform, checked by hash, so the same recording is never included twice.

Wired to the weather
Every map and every weather state your weather mod emits resolves to a bed. A config-closure check proves it before any build is released: no map goes silent, no weather goes silent,
no sound reference dangles. Built and verified against Atmospherics out of the box.

How it stays audible
The engine fades a sound with distance from a reference set in each file, and almost every community file leaves that reference at the tool default, which fades to a whisper within a few metres.
AlifeAmbience raises each file's reference to match where its channel places it, keyed to the sound's character (a sustained tone carries, a sharp transient stays near),
so it decays naturally instead of vanishing. Stereo files, which the engine plays flat at your ears with no direction, are folded to mono so they position in the world.
Loudness is leveled into a band, quiet content lifted and hot content eased, to a calibrated target, as a lossless edit to each file's own data.
The game's ambient volume slider still sets the overall level on top.

Requirements:
Anomaly 1.5.3
A DLTX-capable engine (the modded exes / GAMMA)
A weather mod whose ambient states the bed covers (Atmospherics out of the box)
MCM (optional, for the version footer and diagnostics)

Install (MO2):
1. Install this mod
2. Load it so its ambient config wins (below other soundscape beds you are replacing)
3. Adjust ambient loudness with the game's own sound options if needed

Uninstall (MO2):
Disable or remove in MO2. Weather visuals are your weather mod's job and are untouched.

Compatibility:
Built for GAMMA with Atmospherics, and it runs on vanilla Anomaly and any weather mod whose ambient states the bed covers. It is a bed layer: it wins the ambient sound config and plays the merged bed.
It composes with AlifeSpooks, which places horror one-shots and vetoes its own sounds out of the base channels, so the living bed and the horror never double. It does not touch weather visuals,
emission, or psi-storm.

Credits and permission:
Most of the sounds come from the original S.T.A.L.K.E.R. games and from the standalone builds that carry and rework their audio: Solyanka (NS OGSR), Dead Air, OGSE, Prosector, NLC, OLR,
and Lost Alpha. The community packs that draw on them are used with thanks to their authors: the Dark Signal family and Amplified Soundscape by Shrike, including unreleased interior audio he made;
Audio Expansion by AniHVX; Immersive Ambience Expansion by Kutee; Soundscape Overhaul by Solarint. Every source is either freely licensed or used with the author's permission, granted for my mods,
not tied to any one mod. Every author is credited above; only selected audio is included, and if an author does not want their work included it is removed.
Each source's license and the granting author's permission are recorded in licensing.md; nothing is included without a free license or the author's consent.

Usage and License:
Modpacks are allowed and encouraged. Keep the readme and license files. Addons, patches, and integrations are allowed. Credit "AlifeAmbience by Damian Sirbu" visibly on your mod page.
You may not reproduce the implementation in other software, even with credit. The full license is in the LICENSE file and on GitHub.

Issues and suggestions:
Open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the
GAMMA, EFP, Anomaly, and Zona Discord servers.
Read this readme first.
