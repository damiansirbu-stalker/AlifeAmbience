# next

In development. Initial release.

AlifeSpooks restores the old-school horror of the Zone that modern realism
soundscapes stripped, and adds control over the in-world sound the Zone already plays.
It works ON the game's own sound channels: it enriches the channels your install plays
with net-new dark sounds, restores the horror the GAMMA soundscape strips, and defines
its own channel only where none exists - never a parallel channel, never a duplicate.
It never adds a sound your install already plays, and never repeats a recording within a
channel or a loop bed: identity is decided by the waveform - exact hash, acoustic
fingerprint, then a cross-correlation that tells a re-encoded copy from a genuinely
different sound - so every duplicate is caught without ever merging real variety away.
Every sound is measured (spectral shape,
EBU R128 loudness, length) to decide looped bed vs one-shot; placement is traced from
where the packs used each sound per level, hour and weather, corrected against
S.T.A.L.K.E.R. canon, and capped to a vanilla-like density. Played
periods are tuned so a long sound never overlaps into a wall of noise and a thin channel
never spams its handful, and a runtime no-repeat memory means you do not hear the same
call twice. It overrides no ambient files - DLTX ships the channel definitions and the runtime clone
injects placement - so it layers onto the GAMMA / Dark-Signal base, best-effort elsewhere;
every included sound traces back to its origin mod,
path, channel and settings, and an in-game trace logs each play with the player's location.
Two MCM tabs: Atmosphere (the dark layer, per-layer volume plus no-repeat variety) and
Development (trace level, log flush, and a reset-to-defaults button).

See doc/readme.txt for what it adds and doc/architecture.md for how it is built.
