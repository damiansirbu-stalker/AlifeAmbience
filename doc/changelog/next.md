# next

In development. Initial release.

AlifeAmbience restores the old-school horror of the Zone that modern realism
soundscapes stripped, and adds control over the in-world sound the Zone already
plays. It is built by a tool, not assembled by hand: every sound is measured
(spectral shape, loudness, length), deduplicated to one best copy by content hash,
and loudness-leveled per group without flattening. Placement is traced from where
the source packs used each sound, per level, per hour, per weather, then corrected
against S.T.A.L.K.E.R. canon. It overrides no ambient files, composing through DLTX,
so it layers onto GAMMA, vanilla, or any soundscape; every included sound traces back
to its origin mod, path, channel, and settings, and an in-game trace logs each sound
as it plays. Two MCM tabs: Atmosphere (the dark ambient layer, per-mood control) and
Diegetic (volume and control for in-world radios, megaphones, and campfire instruments).

See doc/readme.txt for what it adds and doc/architecture.md for how it is built.
