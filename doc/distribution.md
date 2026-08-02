# AlifeAmbience - distribution (where each sound plays)

How the five accent moods and five texture beds are placed across the 21 level
presets, per time of day and weather. The rule is EVIDENCE-DRIVEN, then refined by
S.T.A.L.K.E.R. canon for the special levels. Built by `merge.write_presets`
(accents) and `aa_texture.script` (texture bed).

## Method: trace the source, do not invent

The vanilla ambient section name carries time (`day`/`evening`/`morning`/`night`)
and weather (`rain*`, `pre_storm`, `storm_*`, `tuman*`) plus the indoor set. For each
of our 21 level presets and each section, `_section_moods` aggregates across all four
source packs (Dark Signal Weather, Soundscape, RETUNE, Dark Signal Amplified) which
of OUR channels each author placed in that exact level+section, and maps those to our
five moods. A mood plays there iff a source author placed a channel of that mood
there.

Because the section is time+weather, three behaviours fall out of the source
placement with no extra rule:

- Night heavier than day - night sections carry `out_night_amb`/`out_dark_amb`/night spoops; day-crows drop out after dusk.
- Animals by time - crows by day, owls at dusk/night.
- Weather-gated - the weather mood appears only where the packs placed storm/rain/fog.

## Lore overrides (the two the generic packs got wrong)

The source packs treated a few special levels generically. Two are overridden against
canon:

- Underground labs (`environment_underground`, `_more`, `_x18` = Lab X18): the source only wires them in `indoor*` sections, so they get the `underground` mood there and NOTHING in the surface hours. Structural, not taste.
- `environment_whisper` (the haunted level): reduced to `dread` + `weather` - no wildlife, no people.

## Per-area profile (canon x placement)

| preset | canon area / terrain | human | atmosphere | placement |
|--------|----------------------|-------|------------|-----------|
| cemetary | Truck Cemetery - rusted vehicle graveyard, open junk | light | eerie, exposed | dread+weather+animal+light human |
| darkscape | Darkscape - dark wooded rocky valley, road/tunnel | light (bandits) | oppressive, dim | dread-heavy+animal+weather |
| field | open fields (Cordon/Agroprom) - grassland, marsh edge | moderate | windswept | full |
| forest | forested levels - dense canopy | moderate | enclosed, little sky | dread+animal+human, less weather |
| garbage | Garbage - junkyard reclaimed by nature | moderate (bandits) | desolate | full |
| generators | Generators - irradiated forest+industrial, Monolith | Monolith | irradiated, tense | dread+human heavy+weather, some crows |
| hospital | Pripyat/Limansk hospital interior | none (ghost) | claustrophobic, decay | dread+human+light animal, low weather |
| jupiter | Jupiter (CoP) - factory+fields+underground, all factions | heavy | industrial, mixed | full incl human |
| npp | Chernobyl NPP - reactor, Monolith, sarcophagus | Monolith | irradiated, dark_signal | dread+human heavy+weather, some crows |
| pripyat | Pripyat - overgrown ghost city, Monolith/zombies | Monolith | haunting ruin | dread+human+animal, low weather |
| pripyat_outskirts | Pripyat approach - ruin + field edge | Monolith/loner | ruin, exposed | as pripyat |
| rostok | Rostok/Bar - Duty hub, industrial urban | HEAVY (safe hub) | populated, industrial | human+dread+animal (dread should be rarer here - future) |
| rostok_wild | Wild Territory - industrial ruins, bloodsuckers/snorks | mercs (light) | ambush, tense | dread heavy+human+animal+night spoops |
| swamp | Great Swamps - marsh, willows, water, fog | light (Clear Sky) | foggy, wet, eerie | full+weather(fog) heavy+animal |
| underground | generic tunnels/sewers/catacombs | none | dripping, claustrophobic | underground only, indoor |
| underground_more | more tunnel variants | none | claustrophobic | underground only |
| underground_x18 | Lab X18 - dark lab, poltergeists/controllers/burers | none | darkest, psi, machinery | underground only |
| urban | Dead City / Limansk ruins | mercs/Monolith | desolate urban | dread+human+animal, low weather |
| whisper | haunted whisper level | none | HAUNTED, whispering | dread+weather only (override) |
| yantar | Yantar - dead lake/swamp, scientist bunker, zombies | Ecologists+zombies | PSI, sickly, foggy | dread(psi spoops)+human(sci drones)+weather+animal |
| zaton | Zaton (CoP) - dried swamp, shipwrecks, industrial | loners/bandits | desolate wetland, foggy | full+weather+animal |

The study is a validation: the evidence placement already agrees with canon for 19 of
21 levels, and the 2 specials are the overrides above. That is the point of tracing
the pack authors' own placement rather than hand-authoring a table.

## Texture pools and per-level selection (`aa_texture.script`)

Six looped pools, one audible at a time, chosen at runtime by `want_bed`, priority:

1. underground (engine `underground` event) -> LAB pool on the X-Lab levels (`level.name()` in `l04u_labx18`, `l08u_brainlab`, `l13u_warlab`, `labx8`, `l12u_control_monolith`, `l12u_sarcofag`: machine, metal, voices, banging), else the SEWER pool (drip, rats, ambient, drone) for tunnels and bunkers.
2. weather: storm or rain factor > 0.3 -> stormrain; foggy/tuman -> fog; any rain -> stormrain.
3. time of day (`level.get_time_hours`): dusk-to-dawn (>=20 or <6) -> the dread drone-bed; daylight -> the lighter wind-bed.

The lab/sewer split is where the held texture surplus gets used: each pool now ships
up to 40 loops (was 15), drawing ~155 more of the previously-held sounds, and a lab
draws from a different pool than a sewer. The underground material carries a
channel-character signal (lab machinery vs tunnel drip) but NO per-individual-level
tag, so the split is per-CLASS (lab vs sewer), not per-level (Yantar-underground vs
Zaton-underground) - the latter would be invented, not traced, so it is not done.
Level.name() -> lab is taken from the game's own ambient configs.

## Decisions on record

- animal at `npp`/`generators`: KEEP. Crows are carrion birds, canonically present across the Zone near death and ruin; the animal mood is one rare channel (mostly crows), so it reads as occasional crows over a dead reactor, which is correct. The source evidence stands.
- Rostok/Bar is the Zone's safe hub; its dread should be rarer, not absent. That needs a per-area rarity lever (a period multiplier), which is future MCM/rarity work, not a placement change.

## Reproduce

`python3 tools/merge.py deploy` regenerates the 21 `mod_environment_*_alifeambience.ltx`
presets from `classification.json` + the source configs. The per-level, per-section
mood set is a pure function of the source placement plus the two overrides above.
