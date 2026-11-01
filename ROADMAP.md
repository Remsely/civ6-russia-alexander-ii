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

**Status:** implementation prepared; in-game testing and voice polishing continue. The release has not been published.

- [x] Rework the ability: from the Industrial Era, +1 Builder charge, +1 Food per two adjacent Farms (tiers at 2/4/6), a one-time Governor title and +10% growth for cities with an assigned Governor; remove Pasture Production and the unit upgrade discount.
- [x] Implement the railway network: each city gets +1 Production per rail-connected own city (capped by the receiving city's Population) and +1 Gold per rail-connected foreign city. A Capital connection is not required; city-states and civilizations at war count. Gathering Storm is required.
- [ ] Complete in-game checks of the ability, railways, save/load and compatibility ([TESTING](docs/en/TESTING.md)).
- [x] Select a Russian voice and integrate six core diplomacy recordings on Windows; the user confirmed the earlier build on November 1, 2026 after loop, duration and speech-stop fixes.
- [x] Prepare recordings for all 31 diplomacy texts, including the other 24 lines and the second defeat variant; integrate trial routing, separate audio selection for the two DEFEAT texts, and full Russian loading narration.
- [ ] Test the new loading narration and volume, extended dialogue and both defeat variants in game; refine takes with outstanding feedback. [Voice audit (Russian)](docs/voice-coverage.ru.md).
- [ ] Select and integrate an English narrator for the loading screen only; test narration language selection. Alexander's dialogue stays Russian in every interface language, with RU/EN subtitles.
- [ ] Complete text review, final checks, release versioning and packaging. [Draft release notes](docs/v2.0.0-alpha-release-notes.md). [Release preparation checklist](docs/v2.0.0-alpha-release-checklist.md).

## v2.5.0 — a living leader

- [ ] Refine the 3D model based on feedback.
- [ ] Add movement animations for different diplomacy situations.
- [ ] Before reworking the 2D backgrounds, inspect the number and purpose of vanilla leaders' separate loading and diplomacy backgrounds; distinguish independent variants from parallax layers. Determine whether the game supports switching backgrounds between diplomacy scenes/situations and assess whether Alexander would benefit from different backgrounds. If supported and useful, define the variants and test switching with one prototype.
- [ ] Improve the 2D backgrounds on the loading and diplomacy screens based on the findings.

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
