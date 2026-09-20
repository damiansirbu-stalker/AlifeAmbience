Version: 1.0.0-snapshot (xlibs 1.8.3, demonized 20250908)
Changelog: https://github.com/damiansirbu-stalker/DiegeticAmbience/blob/main/doc/changelog

My work:
GitHub: https://github.com/orgs/damiansirbu-stalker/repositories
ModDB: https://www.moddb.com/members/damian-sirbu/addons
Nexus: https://www.nexusmods.com/profile/damiansirbu/mods

My contributions:
X-Ray Monolith: https://github.com/themrdemonized/xray-monolith

[ HERO IMAGE: diegeticambience-hero.gif - a living ambience for every map, weather, and hour ]

Most of the ambient audio installed in Anomaly is never heard, and fixing that takes every step of the chain:
which packs to draw from, which sounds inside them to keep, listening to each one, the parameters written into every ogg, the calculation behind those parameters, and the removal of duplicates.
A lot of the sounds worth hearing are old, from the original games and the standalone builds that came after, and I wanted those in the Zone too.
The audio is lost in the struct parameters, in the stereo channel count, and in the duplicates.

Every ogg carries a binary struct holding min_distance, max_distance, base_volume, a game type and an AI hearing distance, and any ffmpeg pass strips it.
Without it a file falls back to min 1 and max 300. X-Ray's linear fade and OpenAL's inverse rolloff together put such a file 26 to 31 dB down at a 25 to 50 metre placement.
Only mono plays in 3D. A stereo file force-plays 2D, listener-relative, outside the distance model and outside occlusion, and about half of what the packs ship is stereo.
Channel count is what the engine checks, so a dual-mono file behaves as stereo.
The same recording also travels between packs under different names and encoders, so one channel can hold three copies of it.

DiegeticAmbience measures every file and writes the struct against where the sound is placed. The audio pages are unchanged.

The soundscape carries its own dread. The distant screams, the night spooks and the dark ambience play with no other mod installed.
DiegeticDread is optional on top. Its director places dynamic horror sounds where and when they hurt most.
When both run, DiegeticDread takes its captured sounds out of the base channels at load, so the two never double.

------------------------------------------------------------------------------------------------------------------------------------

Every ambient pack in this space was checked for channel count and sample rate.
Across them, 5 to 49 percent of files are stereo, which the engine plays flat at the ear with no distance falloff, and some sit at the wrong sample rate and play as silence.
Every file here is mono at 44100, and the release does not build unless both counts stay at 0.

The packs each cover part of the problem.
The biggest has the most sounds and the widest level coverage. Its beds play too quiet, and about half its files are stereo.
Another plays loud enough. It covers fewer levels.
None of them rewrite the per-file audio settings that decide whether a sound is heard.
DiegeticAmbience takes sounds from several of these packs and does that audio work, so each one plays loud enough to hear across a wide set of levels.
Loudness is measured per file and written into the struct, where the other packs ship each recording as it came.
The configuration covers the most levels here, 33 levels and 31 presets, and every cell of the weather matrix resolves to real audio.
The content is the best of 7 packs in one: Dark Signal structure and birds, Soundscape Overhaul wind, Audio Expansion insects and frogs, Immersive Ambience helicopter.
Thunder plays as rumble in the storm states and as claps at the vanilla strike paths, positioned and delay-corrected by the engine, with the weather mod timing untouched.
Duplicates are resolved across all the sources, every exclusion is written down, and the licence basis is recorded per source.

The engine also carries a weather-effect layer: gusts of wind with fog wisps and one recording, fired on a timer in every outdoor state.
That layer is dead in the whole lineage.
The Dark Signal configs strip its keys, and the Atmospherics effects file points all ten sounds at files that exist in no archive, so the presets that kept the keys play them silent.
Here the ten effects fire in every outdoor state, and their sounds are pinned to recordings proven present, on stock Anomaly and under Atmospherics alike.
During emissions the four vanilla surge bed channels play again, where the ancestors of this configuration had muted them.

------------------------------------------------------------------------------------------------------------------------------------

Sources

Classic S.T.A.L.K.E.R. audio - nearly every ambient recording in the Zone descends from GSC's originals, reworked across two decades of standalone builds.
Solyanka (NS OGSR), OLR, OGSE 0693, Dead Air, Lost Alpha, NLC Improved, Prosector, and Anomaly 1.5.3 itself.
Dark Signal Amplified Soundscape, by Shrike - the level and weather configuration, and the birds.
It is the only pack that covers all 33 levels, extended maps included, in every Atmospherics state, which is why the configuration is built on it.
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
A file arriving with no struct at all is given one, with max taken at 100 metres, the median of the corpus (the engine default is 300).

Mono - the fold produces a genuine single-channel file, because the engine spatialises on channel count.
Left and right are summed, unless the pair is anti-phase (side RMS more than 3 dB above mid, where summing would cancel it) and the left channel is kept on its own instead.
It is a libvorbis re-encode at quality 6, resampled to 44100. The re-encode strips metadata, which is why the author's struct is read out and stored before the fold runs.

Distance - min_distance is floored against where the channel actually places the sound, and the crest factor picks the ratio.
A hard attack takes 0.40, a sustained tone takes 0.60.
The floor is held under 80 percent of max_distance so that a real fade band always survives between the two, and it never lowers a value an author set deliberately.

Loudness - base_volume is levelled into a band with a floor and a ceiling. Continuous beds aim at -30 LUFS effective and single sounds at -36, with ceilings at -24 and -28 to bring down anything hot.
The figure is computed from content loudness plus both rolloff terms, so it refers to what arrives at the placement.
It closes 70 percent of a file's gap, so quiet recordings stay quieter than loud ones.

Lossless - both corrections are written into the comment struct and nowhere else, so the audio pages come out identical to what the author encoded.
The mono fold is the only exception, because the engine positions mono only.

Spawn radius - the min and max in sound_channels.ltx are a different pair from the ones inside the file, and the two are easy to confuse.
They decide where around you the scheduler drops a sound, not how loud it is once it is there.
A sound spawned near its own max_distance is placed where the curve reaches zero. Wind was spawning to 200 and inaudible at that range, so it is capped at 130.

Duplicates - an md5 catches the files that are byte for byte the same. Chromaprint catches the ones a hash cannot see, the same recording renamed or run through another encoder.
Every duplicate pair is reported, and the configuration keeps one copy per recording, so a channel never draws the same sound twice under two names.

Channels - a channel is a pool the engine draws from at its own rate, so the number of channels in a preset is the number of things arriving at you per minute.
One channel holds one voice: one coherent recording family with its own placement and its own cadence, capped at 40 sounds.
New content arrives as new channels paying for themselves in cadence. The variety grows while the rate stays flat.

Terrain - which presets count as wetland, forest, field or urban comes from joining the level configuration against the terrain of each map.
The names do not match the terrain. environment_forest is used by a field map and environment_darkscape by Red Forest.

Culling - anything measuring at or below -60 LUFS leaves through the exclusions register. No channel is left empty.

Repairs - the stock configuration ships four channel references that resolve to nothing, wind_trong for wind_strong among them.

Coverage - 33 levels, 31 presets, 12 ambient states, the same set under stock Anomaly weather and under Atmospherics.
Every cell of that matrix has to resolve to a real channel with real audio behind it, and the build will not produce a release until it does.

Measurement - ffmpeg does the reading, ebur128 for integrated loudness in broadcast LUFS and astats for crest factor and true peak, with Chromaprint handling identity.
All of it feeds a reconstruction of the two rolloffs and the effects master, so every number in the build refers to what arrives at the player.

Reproducible - I choose the channels and the files by hand, and the config records those choices.
One command pulls those files from the packs and masters them, so the audio comes out the same every time.
Every file in the release traces back to its source pack and the measurement that shaped it.

Offline - none of this runs against your install, and the build downloads nothing.
I pull the packs by hand, and licensing.md records the basis for every source.

------------------------------------------------------------------------------------------------------------------------------------

Engine and scripts

Most of this mod is audio. The rest is engine and script work, planned, for the parts a file cannot carry.
All of it waits on one engine change: a hook at the point where X-Ray decides to play an ambient sound, so a script can inspect the pick before it plays.
xlibs carries the API, and the trace consumer is built, both inert until a public engine ships the hook.

Beds on first load - the engine does not render the ambient beds on a fresh run until you have saved and reloaded.
Tracing - report what the ambient system does while a build plays.
Throttling - the ambient system fires the same sound twice in a row, or three at once. A minimum gap at the emitter and a short history of recent plays prevent both.
Families - related sounds selected together, so a location keeps a consistent character over several minutes.
Jitter - a few metres of variation on the emit distance, bounded to stay inside the author's band.

------------------------------------------------------------------------------------------------------------------------------------

Requirements

Anomaly 1.5.3
xlibs - https://www.moddb.com/mods/stalker-anomaly/addons/xlibs-1001
Modded exes: themrdemonized 20250908 or newer, or AOEngine v0.55 or newer. The full feature set needs the latest demonized build. A feature that needs a newer one stays inactive on older exes.
No weather mod is required. Stock Anomaly weather and Atmospherics emit the same ambient states, and the soundscape covers all of them
MCM - optional, for the version footer, the wiring inspector, and the sound player toggle

Install (MO2)

1. Install xlibs
2. Install DiegeticAmbience
3. Give it higher MO2 priority than any other ambient or soundscape mod, so its configuration wins
4. A weather mod is optional. Stock Anomaly weather works as is. Atmospherics is what this is built and verified against
5. Set the level in the game's own sound options. There is no volume slider in the mod, because loudness is already levelled into each file

GAMMA - Atmospherics already ships, so the weather side is covered. Disable 304- Dark Signal Weather and Ambiance Audio, 3- Soundscape Overhaul,
G.A.M.M.A. Soundscape Overhaul and G.A.M.M.A. Dark Signal Audio Lite, so that nothing leaks through. DiegeticDread is optional, for the directed horror layer.

Uninstall - disable or remove it in MO2. Weather visuals belong to your weather mod and are untouched.

Compatibility

Weather mods - none required. Stock Anomaly and Atmospherics use the same ambient state names, and the soundscape covers them all.
Another weather mod works if its ambient states are covered. Weather visuals, emission and psi-storm are left alone.
Soundscape mods - this is the ambient layer, so it wins the ambient sound configuration and plays the merged soundscape.
DiegeticDread - optional. DiegeticAmbience plays its own spook sounds standalone. Install DiegeticDread for the directed, dynamic horror on top.
It takes its captured sounds out of the base channels, and the two never double up.
Saves - install or remove it whenever you like, since it is configuration and sounds with no save state.
Tested - Anomaly 1.5.3, GAMMA, and Forgotten Zone.

------------------------------------------------------------------------------------------------------------------------------------

Credits

Solarint made Soundscape Overhaul. Shrike made the Dark Signal family and Amplified Soundscape, and he also gave me his unreleased interior audio for DiegeticDread.
AniHVX made Audio Expansion. Kutee made Immersive Ambience Expansion.

Through those packs this soundscape carries audio from the original S.T.A.L.K.E.R. games and from the standalone builds that reworked it, credited by the pack authors on their own pages.
Each pack carries a free licence or its author's permission, granted for all my mods together, and licensing.md records the basis for each.
I include only selected audio, and if an author does not want their work included, I remove it.

How It's Built:

Although it started from work by Demonized, Alundaio, and Tronex, the current code and patterns are original, learned through reverse-engineering X-Ray, load testing, and custom X-Ray changes.
The design favors the engine's own mechanisms and minimal intervention, with event-native pub/sub over polling.
Work spreads across frames through deferred queues and rate limiters, while per-level caches replace world scans.
The raycasting and range math are hand-written and tested live, and the code follows the engine's own standards and flags.
Performance is the first invariant. Every flow stays under 2ms, and the build rewrites or drops anything that misses.
Profiled continuously with JitProfiler, an engine-native scientific tool. Manual tests run on unoptimized, single-threaded exes.
The code carries tracing and monitoring from the ground up, with every flow timed off the log level.
Every commit runs the full pipeline locally and in CI: luacheck, a Selene build compiled for STALKER with flags the public build lacks, and a load test that runs every script against engine stubs.
Rule layers then check crash safety, hotpath cost, engine correctness, complexity, architecture contracts, security, and the docs.
Every mod is configurable through MCM or LTX, down to each rate, threshold, and toggle, with nothing tunable left hard-coded.
The mod avoids writing engine values, holding its own state in parallel. Any value it must change stays inside the engine's own bounds, so save corruption is impossible.
The family runs on one rulebook through xlibs. Every rule, policy, and check is one shared implementation, the same protection, distances, faction logic, and combat reads in every mod.
It depends on no other mod, not even my own. The only shared layers are X-Ray and xlibs.

[Screenshot: DiegeticAmbience under JitProfiler, a live CPU and allocation capture]
Project Health: https://damiansirbu-stalker.github.io/DiegeticAmbience/

Usage and License:
  Modpacks: allowed and encouraged. Keep the readme and license files.
  Addons, patches, integrations: allowed. Credit "DiegeticAmbience by Damian Sirbu" visibly on your mod page.
  Reproducing the implementation in other software: not allowed, even with credit.
  Full license in LICENSE file and on GitHub.

Diagnostics and reporting:
Development > Log level: set to DEBUG, reproduce, then back to WARN. Writes diegeticambience.log.
Development > Enable the sound player: opens the channel review player on PageUp to audition every ambient channel.
Report at https://github.com/damiansirbu-stalker/DiegeticAmbience/issues/new/choose or the EFP, Anomaly, and Zona Discord. Include repro steps, engine build, modlist, load order, xray.log, and the debug log.

Tags: engine-native, performance, save-safe, diegetic, audio, ambient, soundscape, audio-engineering, measured, lossless, 3d-sound, audible, curated, weather-audio, classic-audio, dynamic, emergent, sound-harmony, complete, engineered
