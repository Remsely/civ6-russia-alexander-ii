# Roadmap: Remsely’s Russian Empire: Alexander II

[Русский](ROADMAP.ru.md) · [Ideas bank](docs/en/ideas.md) · [Release history](CHANGELOG.md)

The release order reflects the agreed direction. Dates are unset; mechanics that still need design or testing are identified below.

## v1.5.0 — 3D leader

**Status:** the leader and later idle animation are implemented; the user confirmed the corrected animation works in game.

- [x] Leader model and diplomacy idle animation.
- [x] Eye and attachment fixes.
- [ ] Complete in-game checks of the other changes, text review and release preparation.
- [ ] Finish migrating and updating documentation.

## v2.0.0 — reforms and voice

- [x] Rework the ability: from the Industrial Era, +1 Builder charge, +1 Food per two adjacent Farms (tiers at 2/4/6), +1 Governor title and +10% growth for cities with an assigned Governor; Pasture Production and the unit upgrade discount removed.
- [x] Implement the railway network: a city connected to the Capital by rail gets +1 Production and +1 Gold per foreign rail-connected city, with no design cap (the tier machinery's technical bound is 200 foreign cities); Gathering Storm is a hard dependency.
- [ ] Complete the in-game checks of the ability and the railway network ([docs/en/TESTING.md](docs/en/TESTING.md)).
- [x] Select a voice and integrate six Russian diplomacy recordings on Windows; the user confirmed the current build on November 1, 2026, following duration/loop and speech-stop fixes.
- [ ] Record and integrate RU/EN loading narration and the second defeat text with separate audio selection; verify redistribution terms. [Voice audit (Russian)](docs/voice-coverage.ru.md).
- [ ] Consider voicing the other 24 lines after completing the minimal set.

## v2.5.0 — a living leader

- [ ] Refine the 3D model based on feedback.
- [ ] Add movement animations for different diplomacy situations.
- [ ] Improve the 2D backgrounds on the loading and diplomacy screens.

## v3.0.0 — unique district and speech

- [ ] Create a financial unique district and State Bank building; design original mechanics closer to implementation.
- [ ] Research and implement mouth movement timed to speech; first test synchronization with one line.

## v3.5.0 — military reform

- [ ] Add a unique unit: a Berdan rifleman is the candidate. Determine bonuses during development.

## v3.7.0 — natural wonder

- [ ] Add the Lena Pillars; determine mechanics and visual execution during development.

## v3.8.0 — city-state

- [ ] Add a historical city-state from Alexander II's era: choose between Frankfurt and Lübeck during implementation.
- [ ] Check the name against Germany's city list and compatibility with installed mods.

## Earlier release

v1.0.0-alpha was published. See the [changelog](CHANGELOG.md); the previous plan is preserved in [the archive](docs/roadmap-archive.md).
