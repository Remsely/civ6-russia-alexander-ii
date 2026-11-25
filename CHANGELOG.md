# Changelog

[Русский](CHANGELOG.ru.md)

## v2.0.0-alpha — Unreleased

- Extend the Liberator agenda with +3 for a shared religion and −12 for conversion of Alexander's own cities under the game's standard condition. Set AI preferences for founding Eastern Orthodoxy and for Holy War when available. Cumulative penalties and reactions to conversion of foreign cities are outside the alpha's scope.
- Rework the Great Reforms: Industrial Era Builder charges, a one-time Governor title and growth for cities with a Governor. Remove the old Pasture, unit-upgrade and Farm adjacency bonuses.
- Add railway Production from connected own cities and Gold from connected foreign cities; each bonus is capped separately by local Population. No Capital connection is required. Gathering Storm is required.
- Reduce railway recalculation and modifier overhead with cached network components and binary-weighted bonuses. Migration of older saves still needs in-game verification.
- Integrate Russian recordings for 31 core diplomacy texts on Windows, with separate selection for both defeat texts, and loading narration in Russian and English. Add trial routing and RU/EN subtitles for 137 additional statements, agenda reasons and trade-interface lines. Part of the added coverage still needs in-game verification.
- Restore the native era introduction before Alexander's loading narration, using the selected audio language and suppressing Peter's leader segment.
- Expand and revise RU/EN loading and diplomacy text; preserve selected takes, generation settings and listening feedback.
- Update audio validation, listening catalog, documentation and agent skills.

The player confirmed playback on the loading screen and when concluding a trade deal. Checks still cover the latest diplomacy exit-button fix, trade edits and subtitles, both defeat variants, loading across eras and audio languages, reforms, railways, the religious agenda and saved games. See the [release checklist](docs/v2.0.0-alpha-release-checklist.md).

## v1.5.0-alpha

- Add the animated 3D Alexander II leader and a diplomacy background.
- Fix eye geometry and bone bindings; add automated checks for cooked leader bindings. The corrected animation was confirmed in game.
- Revise Alexander's city list and change the farm adjacency bonus from Production to Food.
- Update the 3D build pipeline, bilingual documentation and roadmap.

The release remains an alpha: gameplay and compatibility checks continue. Windows was tested in game; macOS has not been tested in game.

## v1.0.0-alpha

First public alpha release; some mechanics still required in-game verification at release.

- Alexander II as an alternate leader of Russia, with the Great Reforms ability (Builders, Pastures, Farms, Zemstvos and unit upgrades).
- The Liberator agenda and 31 diplomacy lines.
- Eleven new city names, including Odessa, Sevastopol, Vladivostok, Tashkent and Samarkand, at the start of Russia's list; Saint Petersburg as capital.
- Black-and-gold colors, portrait, icon, loading and diplomacy backgrounds.
- Loading text and Civilopedia page, without a quote pending verification against printed sources.
- English and Russian text; Windows and macOS BLPs (macOS was not tested in game).
