================================================================================
  ALIFEAMBIENCE
  A dark-mood ambient overlay for S.T.A.L.K.E.R. Anomaly / G.A.M.M.A.
================================================================================

AlifeAmbience layers the Zone's dark side over your existing ambience. It gathers
the dreadful, horror, and mournful sounds from several soundscape packs, keeps the
best-quality copy of each, and adds them on top of whatever ambient mod you run.
It does not replace your soundscape - it composes onto it through DLTX, so it works
alongside GAMMA's ambience, vanilla, or any other soundscape.

What it adds
------------
- Dread: distant mutant growls, far-off screams, spooks, dark ambience, the dark-signal cue.
- Underground horror: the full tunnel and lab set - whispers, rats, banging, metal groans, drips.
- Tension: distant gunfire, ominous drones, creeping wind, branch creaks.
- Eerie atmosphere: owls, distant dogs, crows, fog.
- Oppressive weather: storms, rain, howling wind.

What it does NOT touch
----------------------
- Generic daytime life (birdsong, insects, plain wind, pleasant tree/foliage) - your
  base ambience keeps providing those.
- Emission and psi-storm sound - left to their own systems.

How it works
------------
A DLTX overlay: it adds and fills the dark channels and switches them on per map and
time, without overwriting the base ambient files. Distances and firing rates are set
to the softest and rarest values any source pack uses, and the number of layers per
location is capped so it stays atmospheric, not noisy.

Installation
------------
Content and configuration only; no scripts. As a DLTX overlay it can load at any
position. Requires 44.1 kHz OGG playback (the Anomaly standard).

Credits
-------
AlifeAmbience owns only the configuration. All audio is drawn from these community
packs, with thanks to their authors:

    Dark Signal Weather and Ambiance   - Shrike
    Dark Signal Amplified Soundscape   - Shrike
    Soundscape Overhaul                - Solarint
    RETUNE Ambient Sounds              - Aphrodite_child

Used under the terms on each source page; only the selected audio is redistributed,
with attribution. If an author requests removal, their pack is dropped from the build.

(The full per-channel sound table and final counts are filled in once the build is
complete; see doc/architecture.md for the method.)
