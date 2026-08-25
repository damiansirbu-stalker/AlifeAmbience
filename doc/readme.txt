AlifeAmbience: a curated, audible ambient soundscape for STALKER Anomaly, by Damian
Version: next (xlibs required)
GitHub: https://github.com/damiansirbu-stalker/AlifeAmbience
Changelog: https://github.com/damiansirbu-stalker/AlifeAmbience/blob/main/doc/changelog
Bugs, suggestions: https://github.com/damiansirbu-stalker/AlifeAmbience/issues

Alife Collection:
AlifeAmbience: https://github.com/damiansirbu-stalker/AlifeAmbience
AlifeBalance: https://www.moddb.com/mods/stalker-anomaly/addons/alifebalance
AlifeCompanions: https://github.com/damiansirbu-stalker/AlifeCompanions
AlifeDiegetic: https://www.moddb.com/mods/stalker-anomaly/addons/diegetic-audio-control-100
AlifeGuard: https://www.moddb.com/mods/stalker-anomaly/addons/alifeguard-1001
AlifePlus: https://www.moddb.com/mods/stalker-anomaly/addons/alifeplus-v1-0-01
AlifeSpooks: https://github.com/damiansirbu-stalker/AlifeSpooks
AlifeTactics: https://www.moddb.com/mods/stalker-anomaly/addons/alifetactics
FurnitureFuel: https://github.com/damiansirbu-stalker/FurnitureFuel
JitProfiler: https://github.com/damiansirbu-stalker/JitProfiler
TestZone: https://github.com/damiansirbu-stalker/TestZone
xlibs: https://www.moddb.com/mods/stalker-anomaly/addons/xlibs-1001

I built this for my own game. Most of the ambient audio installed in Anomaly is never heard, and fixing that takes every step of the chain:
which packs to draw from, which sounds inside them to keep, listening to each one, the parameters written into every ogg,
the calculation behind those parameters, and the removal of duplicates. Three of those steps are where the audio is lost.

Every ogg carries a binary struct holding min_distance, max_distance, base_volume, a game type and an AI hearing distance, and any ffmpeg pass strips it.
Without it a file falls back to min 1 and max 300, and X-Ray's linear fade and OpenAL's inverse rolloff together put it 26 to 31 dB down at a 25 to 50 metre placement.
Only mono plays in 3D. A stereo file force-plays 2D, listener-relative, outside the distance model and outside occlusion, and about half of what the packs ship is stereo.
Channel count is what the engine checks, so a dual-mono file behaves as stereo.
The same recording also travels between packs under different names and encoders, so one channel can hold three copies of it.

AlifeAmbience measures every file and writes the struct against where the sound is placed. The audio pages are unchanged.

AlifeSpooks plays the horror one-shots and removes them from the base channels. AlifeAmbience covers the nature and weather ambience. Run both.

------------------------------------------------------------------------------------------------------------------------------------

Sources

Classic S.T.A.L.K.E.R. audio - nearly every ambient recording in the Zone descends from GSC's originals, reworked across two decades of standalone builds.
Solyanka (NS OGSR), OLR, OGSE 0693, Dead Air, Lost Alpha, NLC Improved, Prosector, and Anomaly 1.5.3 itself.
Dark Signal Amplified Soundscape, by Shrike - the level and weather configuration, and the birds. It is the only pack that covers all 33 levels,
extended maps included, in every Atmospherics state, which is why the configuration is built on it.
Soundscape Overhaul, by Solarint - the environment core, meaning wind, weather, birds and foliage.
Audio Expansion, by AniHVX - the insects and the frogs, which nothing else in the set has.
Immersive Ambience Expansion, by Kutee - wind reinforcement and the helicopter.
Dark Signal interior audio, by Shrike - material he made for Dark Signal and never released, given for my mods.

Merging the packs whole measured and sounded worse than any of them alone, because the same wind arrives four times from four authors who each mixed it against a different bed.

------------------------------------------------------------------------------------------------------------------------------------

The build

Ear - the per-category targets come from an in-ear calibration ladder, and the packs were compared by listening before selection.

The struct - five fields, of which the build writes two. min_distance and base_volume are set from measurement.
max_distance, the game type and the AI hearing distance stay exactly as the author left them.
A file arriving with no struct at all is given one, with max taken at 100 metres, the median of the corpus, rather than the engine's 300 metre default.

Mono - the fold produces a genuine single-channel file, because the engine spatialises on channel count. Left and right are summed,
unless the pair is anti-phase, meaning side RMS more than 3 dB above mid, where summing would cancel it and the left channel is kept on its own instead.
It is a libvorbis re-encode at quality 6, resampled to 44100, and it strips metadata, which is why the author's struct is read out and stored before the fold runs.

Distance - min_distance is floored against where the channel actually places the sound, and the crest factor picks the ratio.
A hard attack takes 0.40, a sustained tone takes 0.60.
The floor is held under 80 percent of max_distance so that a real fade band always survives between the two, and it never lowers a value an author set deliberately.

Loudness - base_volume is levelled into a band rather than pushed to a single figure. Continuous beds aim at -30 LUFS effective and one-shots at -36,
with ceilings at -24 and -28 to bring down anything hot. The figure is computed from content loudness plus both rolloff terms, so it refers to what arrives at the placement.
It closes 70 percent of a file's gap, so quiet recordings stay quieter than loud ones.

Lossless - both corrections are written into the comment struct and nowhere else, so the audio pages come out identical to what the author encoded.
The mono fold is the only exception, because the engine positions mono only.

Spawn radius - the min and max in sound_channels.ltx are a different pair from the ones inside the file, and the two are easy to confuse.
They decide where around you the scheduler drops a sound, not how loud it is once it is there.
A sound spawned near its own max_distance is placed where the curve reaches zero. Wind was spawning to 200 and inaudible at that range, so it is capped at 130.

Duplicates - an md5 catches the files that are byte for byte the same, and Chromaprint catches the ones a hash cannot see,
meaning the same recording renamed or run through another encoder, which turned out to be about 1.4 percent of the corpus.
One copy survives and every reference moves onto it, so a channel can never draw the same sound twice under two names.

Channels - a channel is a pool the engine draws from at its own rate, so the number of channels in a preset is the number of things arriving at you per minute.
New content goes into pools that already exist wherever it can, which raises the variety and leaves the rate alone.
Only frogs and the helicopter had nothing to join, so only those two got channels of their own.

Terrain - which presets count as wetland, forest, field or urban comes from joining the level configuration against the terrain of each map.
The names do not match the terrain. environment_forest is used by a field map and environment_darkscape by Red Forest.

Culling - anything measuring at or below -60 LUFS is deleted, along with the references pointing at it. No channel is left empty.

Repairs - the stock configuration ships four channel references that resolve to nothing, wind_trong for wind_strong among them.

Coverage - 33 levels, 31 presets, 12 Atmospherics states. Every cell of that matrix has to resolve to a real channel with real audio behind it,
and the build will not produce a release until it does.

Measurement - ffmpeg does the reading, ebur128 for integrated loudness in broadcast LUFS and astats for crest factor and true peak, with Chromaprint handling identity.
All of it feeds a reconstruction of the two rolloffs and the effects master, so every number in the build refers to what arrives at the player.

Reproducible - the whole soundscape comes back from the source packs with one command, and nothing in it is hand-edited.
Every file in the release traces to the pack it came from and to the measurement that shaped it.

Offline - none of this runs against your install, and the build downloads nothing.
I pull the packs by hand, and a licence check stops the build on any source that is not cleared.

------------------------------------------------------------------------------------------------------------------------------------

Engine and scripts

Most of this mod is audio. The rest is engine and script work, planned, for the parts a file cannot carry.
All of it waits on one engine change: a hook at the point where X-Ray decides to play an ambient sound, so a
script can watch it, refuse it, or alter it first. xlibs carries the API already and it is inert until the
engine calls it.

Beds on first load - the engine does not render the ambient beds on a fresh run until you have saved and reloaded.
Tracing - report what the ambient system does while a build plays.
Throttling - the ambient system fires the same sound twice in a row, or three at once. A minimum gap at the emitter and a short history of recent plays prevent both.
Families - related sounds selected together, so a location keeps a consistent character over several minutes.
Jitter - a few metres of variation on the emit distance, bounded to stay inside the author's band.

------------------------------------------------------------------------------------------------------------------------------------

Requirements

Anomaly 1.5.3
xlibs - https://www.moddb.com/mods/stalker-anomaly/addons/xlibs-1001
Modded exes - themrdemonized or AOEngine, for DLTX
A weather mod whose ambient states the soundscape covers. Atmospherics covers every map and state out of the box
MCM - optional, for the version footer and the wiring inspector

Install (MO2)

1. Install xlibs
2. Install AlifeAmbience
3. Give it higher MO2 priority than any other ambient or soundscape mod, so its configuration wins
4. Keep a weather mod active. Atmospherics is what this is built and verified against
5. Set the level in the game's own sound options. There is no volume slider in the mod, because loudness is already levelled into each file

GAMMA - Atmospherics already ships, so the weather side is covered. Disable 304- Dark Signal Weather and Ambiance Audio, 3- Soundscape Overhaul,
G.A.M.M.A. Soundscape Overhaul and G.A.M.M.A. Dark Signal Audio Lite, so that nothing leaks through. Run AlifeSpooks alongside for the horror layer.

Uninstall - disable or remove it in MO2. Weather visuals belong to your weather mod and are untouched.

Compatibility

Weather mods - any whose ambient states the soundscape covers, Atmospherics included. Weather visuals, emission and psi-storm are left alone.
Soundscape mods - this is the ambient layer, so it wins the ambient sound configuration and plays the merged soundscape.
AlifeSpooks - composes with it. AlifeSpooks places the horror one-shots and takes its own sounds out of the base channels, so the two never double up.
Performance - no gameplay script runs, and nothing polls while you play.
Saves - install or remove it whenever you like, since it is configuration and sounds with no save state.
Tested - Anomaly 1.5.3 and GAMMA.

------------------------------------------------------------------------------------------------------------------------------------

Credits

Solarint made Soundscape Overhaul. Shrike made the Dark Signal family and Amplified Soundscape, and also gave me his unreleased interior audio,
which ships as exclusive content in AlifeSpooks. AniHVX made Audio Expansion. Kutee made Immersive Ambience Expansion.

Through those packs this soundscape carries audio from the original S.T.A.L.K.E.R. games and from the standalone builds that reworked it,
credited by the pack authors on their own pages. Each pack carries a free licence or its author's permission, granted for my mods rather than for one of them,
and licensing.md records the basis for each. I include only selected audio, and if an author does not want their work included, I remove it.

Licence

Modpacks are allowed and encouraged, so long as you keep the readme and licence files. Addons, patches and integrations are allowed.
Credit "AlifeAmbience by Damian Sirbu" visibly on your mod page. You may not reproduce the implementation in other software, even with credit.
The full licence is in the LICENSE file and on GitHub.

Issues and suggestions

Open a report at https://github.com/damiansirbu-stalker/AlifeAmbience/issues/new/choose, or ask on the EFP, Anomaly and Zona Discord servers. Read this readme first.
