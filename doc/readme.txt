AlifeAmbience: a curated, audible ambient soundscape for STALKER Anomaly, by Damian
Version: next (xlibs required)
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

I built AlifeAmbience for my own game. I wanted the most realistic soundscape Anomaly can carry, at the best quality the engine will play.
Every choice in it rests on a measurement rather than on how a file happened to sound to me one evening.

It is the ambient companion to AlifeSpooks. AlifeSpooks plays the horror one-shots and takes them out of the base channels. AlifeAmbience owns the living nature and weather ambience it leaves alone.
Run both.


1. Sources

Nearly every ambient recording in Anomaly descends from GSC's original games, reworked across two decades of standalone builds.
Those builds are Solyanka (NS OGSR), OLR, OGSE 0693, Dead Air, Lost Alpha, NLC Improved, Prosector, and Anomaly 1.5.3 itself.
The modern soundscape packs are what carry that material today, and this mod builds from four of them.

Shrike's Dark Signal Amplified Soundscape provides the level and weather configuration along with the birds.
It is the only pack covering all 33 levels, extended maps included, in every Atmospherics state. Solarint's Soundscape Overhaul provides the environment core: wind, weather, birds and foliage.
AniHVX's Audio Expansion contributes the insects and the frogs, and Kutee's Immersive Ambience Expansion the wind reinforcement and the helicopter.
Shrike also gave me the interior audio he made for Dark Signal and never released.

Merging four packs whole gives a worse soundscape than any one of them alone.
The same wind arrives four times from four authors who each mixed it against a different bed, and you hear the pile rather than the Zone.
Each part of the soundscape therefore takes one pack's version and drops the other three.


2. How it is built

The whole soundscape rebuilds from the source packs with one command, and nothing in the release is hand-edited.
Every choice rests on a number, so loudness, distance and duplication are settled by measurement rather than by a listening session.
A rerun reproduces the release exactly, so changing a calibration value means rebuilding and hearing the difference.
The corrections also reach every file equally, which is the only way a few thousand sounds stay consistent with each other.

The measurements come from ffmpeg. Its ebur128 filter reads integrated loudness in broadcast LUFS, and its astats filter reads crest factor and true peak.
Those two separate a steady background sound from a sharp transient. Chromaprint's fpcalc adds an acoustic fingerprint, which recognises a recording however it was encoded.
Those numbers feed a reconstruction of the engine's own attenuation, so the build works on the loudness that arrives at the player.

None of it runs against your install. Every measurement, correction and comparison happens on my side, against the source packs. The build downloads nothing either.
I pull the packs by hand, and a licence check stops the build on any source not cleared for release.


3. Build stages, and the reason for each

Selection. Every ogg in the four packs is hashed, and one file is chosen for each path the configuration can reference.
Where two packs ship the same path, the audible one wins, so measurement makes the choice rather than a folder pick.

Deployment. The chosen files and the sound routing configuration are copied out.
The surge manager, psi-storm manager, weather graph and thunderbolt settings the packs bundle alongside are never copied, because that logic fights Atmospherics and GAMMA.

Repair. References that point at nothing are fixed or dropped, and the spawn distance of each category is capped.
A reference reading wind_trong instead of wind_strong plays silence, and four such defects were shipping unheard.
Capping wind at 130 instead of 200 stops it sitting out at a range where it reads as nothing.

Wiring. The chosen folders are wired into channels and into the weather sections of every preset. Two of the packs ship no configuration at all, so without this step their audio never plays.
A channel is a pool of sounds the engine draws from at its own rate, so a preset's channel count is how much fires at you per minute.
Almost all of the grafted content extends a pool that already exists rather than adding a channel of its own.
Variety inside a channel goes up, the firing rate stays where it was, and the soundscape gets richer instead of busier. Adding a channel does the opposite.
It is one more sound arriving every minute, forever, on every map that uses the preset. Only two categories had no pool to join.
Frogs play in wetland presets at evening, night and morning, and they sit near you. The helicopter plays outdoors at any hour, as a rare distant pass.
Each inherits its placement from an existing channel of the same character rather than getting invented numbers.
Which presets count as wetland or forest comes from joining the level configuration against the terrain of each map, never from the preset names.
The names lie: environment_forest belongs to a field map and environment_darkscape to Red Forest. Trusting them would have put frogs in dry country.

Acoustic deduplication. Chromaprint fingerprints every deployed file and collapses the copies of one recording a hash cannot see.
Those are the same sound re-encoded or renamed, about 1.4 percent of the corpus.
One copy survives and the references move onto it, so a channel can never draw the same recording twice under two names. That is what keeps a rotation sounding like a rotation instead of a loop.

Pruning. Every file no channel references is deleted. Most of what the packs ship was never wired into anything and never played.

Mono conversion. Stereo becomes mono, for the reason in section 4.

Levelling. Each file is measured once, and both corrections are written from that single measurement.
The first raises min_distance, the value OpenAL uses to decide how fast a sound falls away with distance.
The packs mostly leave it at 1 or 2, so the sound is gone within a few metres of where it plays.
The build raises it to a fraction of where the channel actually places the sound, and the crest factor sets the fraction. A sustained tone takes 0.60 and carries across its area.
A sharp transient takes 0.40 and stays a near detail, because a hard attack that carries too far reads as artificial.
The second correction moves base_volume into a band, lifting a quiet file and easing down a hot one. The target is a level I set by ear and then converted through the engine's own gain path.
It closes 70 percent of the gap rather than all of it, so recordings keep their differences and the result is an ecosystem instead of a wall.
Both corrections rewrite only the comment header of the ogg, leaving the audio byte for byte what the author made.

Culling. Files measuring at or below -60 LUFS are silence, so they go and their references go with them. A channel is never left empty.

Verification. The build refuses to release unless the configuration is closed. Every file on disk belongs to a channel, and every reference resolves to a channel that exists and to audio that exists.
Every level binds a preset, underground to underground and surface to outdoor. Every preset covers every weather state the active weather mod emits, so no map can go silent in the rain.
That last check is the only place this mod touches your weather mod. Atmospherics and its 12 ambient states are what it targets and verifies against.

Three rules run through all of it. Density is held down, because clutter is what makes ambience read as a soundtrack rather than a place.
Content joins existing channels, duplicates collapse to one file, unwired and dead audio is deleted, and each category is capped so it cannot spread across the map.
A sound only enters a channel whose distance band suits its character. That is why the crest measurement decides placement, and why a file arriving far off the target is corrected instead of accepted.
The audio itself is left alone. Every correction rewrites the ogg comment header rather than the audio pages, so what you hear is the author's recording at the author's quality.
The one exception is the mono conversion, which has to re-encode.


4. Mono, and why it decides everything

X-Ray places a sound in the world only when the file is mono. Hand it a stereo ogg and it plays flat at both ears at a fixed level, with no direction, no distance falloff and no occlusion.
The sound follows you around the map instead of coming from somewhere in it. About half of the source material shipped that way.

So the build folds stereo to mono. It sums the left and right channels, unless the two are close to opposite in phase, where summing would cancel them and it keeps one channel instead.
This is the only step that re-encodes audio, done through libvorbis at quality 6, and it resamples anything off-rate to 44100.
The author's own distance and volume values are read out before the conversion and written back after, so nothing is lost but the second channel.

What that buys is placement. A bird calls from a tree you can walk towards, wind arrives across a field rather than from inside your head, and a helicopter passes over and away.
Stereo width is worth nothing in a game you turn your head in, and position is worth everything.


5. Engine support

The soundscape also uses changes I made to the X-Ray engine itself. They went in for tracing, so that I could watch what the ambient system was actually doing while a build played.
Measuring a file on disk only takes you so far, and the rest of the answer sits in the engine at the moment it decides to play something.

That tracing is the groundwork for making the ambience react rather than repeat, and three things are planned on top of it.
The ambient system is happy to fire the same sound twice in a row, or three sounds at once, and both give the trick away.
A throttle at the emitter will enforce spacing, and a short memory of what just played will keep a repeat from following itself.
Sounds that belong together should also be chosen together, so a place holds its character across several minutes. And every play of the same file at the same distance sounds like a recording.
A small jitter on placement, a few metres either way, turns it into an event. That variation has to stay small.
Move a sound far and you break the mix its author made, which is the whole thing this build exists to protect.

AlifeSpooks already hooks the sound emitter for its own placement, so this work shares that hook rather than fighting it.


6. Requirements

Anomaly 1.5.3
xlibs (https://www.moddb.com/mods/stalker-anomaly/addons/xlibs-1001)
A DLTX-capable engine, meaning the modded exes: themrdemonized or AOEngine
A weather mod whose ambient states the soundscape covers, with Atmospherics covering every map and state out of the box
MCM, optional, for the version footer and the wiring inspector

Install (MO2):
1. Install xlibs
2. Install AlifeAmbience
3. Give it higher MO2 priority than any other ambient or soundscape mod, so its configuration wins
4. Keep a weather mod active whose ambient states AlifeAmbience covers. Atmospherics is what it is built and verified against
5. The game's own sound options set the overall ambient level. The mod has no volume slider, because the loudness is already levelled into each file

GAMMA players: GAMMA already ships Atmospherics, so the weather side is covered. Disable the soundscape mods AlifeAmbience replaces, so nothing leaks through.
Those are 304- Dark Signal Weather and Ambiance Audio, 3- Soundscape Overhaul, G.A.M.M.A. Soundscape Overhaul, and G.A.M.M.A. Dark Signal Audio Lite. Run AlifeSpooks alongside for the horror layer.

Uninstall (MO2): disable or remove it in MO2. Weather visuals belong to your weather mod and stay untouched.

Compatibility: it runs on Anomaly and on any weather mod whose ambient states the soundscape covers, Atmospherics included.
It is the ambient layer, so it wins the ambient sound configuration and plays the merged soundscape.
It composes with AlifeSpooks, which places the horror one-shots and takes its own sounds out of the base channels. The living ambience and the horror never double up.
It does not touch weather visuals, emission or psi-storm. No gameplay script runs, and nothing polls while you play.
Tested with Anomaly 1.5.3 and GAMMA. Install or uninstall it at any time, because it is configuration and sounds with no save state.


7. Credits and licence

Solarint made Soundscape Overhaul, Shrike made the Dark Signal family and Amplified Soundscape, AniHVX made Audio Expansion, and Kutee made Immersive Ambience Expansion.
Shrike also granted his unreleased Dark Signal interior audio for my mods, and it ships as exclusive content in AlifeSpooks.
Through those packs this soundscape carries audio from the original S.T.A.L.K.E.R. games and from the standalone builds that reworked it.
The pack authors credit those builds on their own pages: Solyanka (NS OGSR), OLR, OGSE 0693, Dead Air, Lost Alpha, NLC Improved, Prosector.

Each pack carries a free licence or its author's permission, granted for my mods rather than for one of them. licensing.md records the basis for each.
I include only selected audio, and if an author does not want their work included, I remove it.

Modpacks are allowed and encouraged, so long as you keep the readme and licence files. Addons, patches and integrations are allowed. Credit "AlifeAmbience by Damian Sirbu" visibly on your mod page.
You may not reproduce the implementation in other software, even with credit. The full licence is in the LICENSE file and on GitHub.

Issues and suggestions: open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the EFP, Anomaly and Zona Discord servers.
Read this readme first.
