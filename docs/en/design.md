# Mod Design — Remsely's Alexander II

> Detailed earlier design notes are preserved in [the historical document](../remselys-alexander-ii.md). For current behaviour, code and in-game tests take precedence.

Design document for the Civilization VI mod: an alternate leader for vanilla Russia.
Russian version: [`../ru/design.md`](../ru/design.md). Game terms follow the glossary in [`terms.md`](terms.md).

## 1. Overview

| Field | Value |
|---|---|
| Mod name | Remsely's Alexander II (kept in both languages; only the description is translated) |
| Type | Alternate leader for the Russia civilization (`CIVILIZATION_RUSSIA`) |
| Leader | Alexander II Nikolaevich, Emperor of All Russia (1855–1881), called the Tsar Liberator |
| Kept from vanilla Russia | Civilization ability Mother Russia, unique unit Cossack, unique district Lavra |
| New in the mod | Leader ability, AI agenda, city list, colors, 3D leader, art, texts |
| Requirements | Rise and Fall or Gathering Storm (Governors and Loyalty are needed for Zemstvos); the Future Era exists only in Gathering Storm |
| Type prefix | `REMSELY_` (e.g. `LEADER_REMSELY_ALEXANDER_II`) |
| Structural reference | JFD's Russia: Elisabeth (`reference/samples/JFD-Russia-Elisabeth`) |

## 2. Localization

The mod must ship two complete localizations: `en_US` and `ru_RU`. Every `LOC_...` key needs a string in both languages, or players see the raw key. Everything is localized: the mod description, leader name and title, ability and its parts, agenda, city names, diplomacy lines, Civilopedia, loading screen.

Game terms must be official, taken from the game's own localization files (see [`terms.md`](terms.md)); never translate tech, era or building names yourself. The validator fails when a key has no pair.

## 3. Leader Ability: The Great Reforms

### 3.1. Emancipation of the Serfs

- Builders get **+1 charge**.
- Each **Pasture** gets **+1 Production**.
- Each **Farm** gets **+1 Food per 2 adjacent Farms** (max +2 at 4). Food, not Production: Russia's civ ability already grants Production on tundra, and stacking Production made the trait too strong. Only Farms count as neighbours. Adjacency is counted in Lua (`mod/Lua/RemselysAlexanderII_Farms.lua`); modifiers read plot properties.

### 3.2. Zemstvo Reform

Cities with an assigned Governor get Culture and Loyalty that grow with the player's eras:

| Era (official names) | Culture | Loyalty |
|---|---|---|
| Ancient Era | +2 | +4 |
| Classical Era | +2 | +4 |
| Medieval Era | +3 | +6 |
| Renaissance Era | +4 | +8 |
| Industrial Era | +5 | +10 |
| Modern Era | +6 | +12 |
| Atomic Era | +7 | +14 |
| Information Era | +8 | +16 |
| Future Era (Gathering Storm only) | +9 | +18 |

### 3.3. Military Reform

Unit upgrades cost **50% less Gold** (vanilla analogue: the Professional Army policy).

### 3.4. Ability texts

Ability descriptions state values explicitly, without references to the Civilopedia. Current texts live in `mod/Text/{en_US,ru_RU}.xml`; the Russian column mirrors them (see [`../ru/design.md`](../ru/design.md)).

## 4. AI Agenda: The Liberator

He likes civilizations that have not declared wars for a long time (threshold ~30 turns) and dislikes those that declared war recently. Implemented in XML without Lua (`MODIFIER_PLAYER_DIPLOMACY_*`).

- Name: The Liberator / «Освободитель»
- Description: Likes civilizations that have kept the peace for a long time. Dislikes those that recently declared war.

## 5. Cities

A leader-specific city list: `CityNames` rows with `LeaderType` and `SortIndex = -1` come before Russia's civilization-wide list (the Sukritact pattern); order within is insertion order. The capital is set separately via `CivilizationLeaders.CapitalName`. Other Russian leaders only see rows with an empty `LeaderType` and are unaffected.

The list (positions 1–21; dates and justifications verified against the 1855–1881 reign):

| # | EN | Justification |
|---|---|---|
| 1 | Saint Petersburg | capital of the empire (`CivilizationLeaders.CapitalName`) |
| 2 | Moscow | second capital, largest city after St. Petersburg |
| 3 | Nizhny Novgorod | the empire's largest fair (from 1817) |
| 4 | Kazan | largest city of the Volga region |
| 5 | Odessa | f. 1794; third city of the empire, main grain port |
| 6 | Kharkov | f. 1656; fourth city of the empire, trade and industry |
| 7 | Sevastopol | f. 1783; Black Sea Fleet base, defence of 1854–55 |
| 8 | Vladivostok | f. 1860; main Pacific port |
| 9 | Khabarovsk | f. 1858; center of the Amur region (Treaty of Aigun) |
| 10 | Blagoveshchensk | f. 1858; center of the Amur Cossack Host |
| 11 | Tashkent | taken 1865; capital of Turkestan Governorate-General |
| 12 | Verny | f. 1854; center of Semirechye |
| 13 | Novorossiysk | f. 1838; main commercial Black Sea port after the 1856 Peace of Paris |
| 14 | Rostov-on-Don | f. 1749; grain trade via the Sea of Azov (vanilla "Rostov" is a different city, Rostov Veliky) |
| 15 | Baku | in the empire since 1813; oil boom from 1872 (indeclinable) |
| 16 | Riga | f. 1201; largest Baltic port |
| 17 | Novo-Arkhangelsk | capital of Russian America (sold in 1867) |
| 18 | Yekaterinburg | mining capital of the Urals |
| 19 | Irkutsk | "the capital of Siberia", gold trade center |
| 20 | Omsk | center of Western Siberia and the Steppe Krai |
| 21 | Tomsk | f. 1604; trade center of Western Siberia, first Siberian university (1878) |

They are followed by the remaining 25 vanilla Russian names (Novgorod, Astrakhan, …, Sergiev Posad) — 45 names after the capital.

Of these, 14 names are new mod keys (`LOC_CITY_NAME_REMSELY_*`) and 6 are vanilla (Moscow, Nizhny Novgorod, Kazan, Yekaterinburg, Irkutsk, Omsk) repeated as leader rows for priority: the game skips their original rows lower in the list as already used — the same mechanism by which vanilla handles St. Petersburg, both the capital and the first list row.

**Samarkand is excluded**: in the game it is a city-state (`CIVILIZATION_SAMARKAND`), and a Russian city of the same name would clash with it on Earth maps.

## 6. Colors (PlayerColors)

Black and imperial gold with a white accent (the 1858 flag colors): primary `#1C1C1C`, secondary `#D4A017`, accent `#F5F1E6`. Inserted via `INSERT ... SELECT` with `Alt1..3` from a vanilla leader (the table has no `TextColor` column — an insert with it silently fails).

## 7. Art

### 7.1. Assets

| Asset | Purpose | Status |
|---|---|---|
| Leader selection portrait | Card on the setup screen | done (`LEADER_..._SELECT`) |
| Diplomacy portrait (fallback) | Diplomacy screen without the 3D scene | done (`FALLBACK_NEUTRAL_...`) |
| Leader icon | Round icon in every atlas size | done |
| Loading screen background | Wide 16:9 frame | done |
| Diplomacy background | Dark hall behind the 3D leader | done (`REMSELY_ALEXANDER_II_1`) |
| Steam Workshop preview | Mod cover | done (`tools/make_preview.py`) |

Sources are in `art/source/`, generation prompts and services in `art/prompts.md`; the build pipeline is [`art-pipeline.md`](art-pipeline.md).

### 7.2. Background compositions

Style: painterly, in the manner of vanilla Civ VI leaders; warm side light on the face, cold winter background. Dress: 1860s–1870s military uniform with epaulettes and greatcoat, mutton-chop sideburns. Palette: black, gold, ivory, winter blue.

- **A. Study in the Winter Palace** (primary). The leader at a desk with the Manifesto of 19 February 1861 and a pen; the winter Neva and the Peter and Paul spire outside the window. "The reformer at work".
- **B. Palace Square in winter.** The leader in a greatcoat by the Alexander Column and the General Staff building, light snow. "The sovereign and the empire".
- **C. Map and treaty.** The leader at a table with a map of Russian America and the 1867 treaty. "The sale of Alaska".

## 8. 3D Leader

Instead of a static portrait, diplomacy uses a full 3D leader: the model in the portrait's pose, uniform, regalia, orders; a 16-second idle loop — looks at the camera, breathes, blinks, steps in place. Built from Blender sources in `art/3d/`; the pipeline is [`art-pipeline.md`](art-pipeline.md). The static fallback portrait remains in the mod.

The backdrop behind the 3D leader is not an asset but the UI: `LeaderScene.lua` lays the diplomacy background texture under the model (see 7.1).

## 9. Texts

Written and wired (both languages): leader name and title, ability and its parts, agenda, 31 diplomacy lines, Civilopedia article (with history), loading screen paragraph, mod description. The loading screen **quote is not wired**: wordings are not verified against print editions (rules and candidates below).

### 9.1. Quote rules

Only words Alexander II actually spoke or signed may appear as quotes. Invented lines are never formatted as quotes; diplomacy lines are authorial text, not quotes. Candidates:

| Role | EN | Source | Status |
|---|---|---|---|
| Primary | "It is far better that it should come from above than from below." | Speech to the Moscow nobility, 30 March 1856 | Wording found only on an amateur site — verify against a print edition |
| Spare 1 | "We live in such an age that, in time, this must come to pass." | Same speech, after Tatishchev (1996, vol. 1, p. 331) | Verify spelling |
| Spare 2 | "Cross thyself, Orthodox people, and call with us upon God's blessing for thy free labour." | Manifesto of 19 February 1861 | Confirmed by a secondary source; probable author is Metropolitan Filaret; in-game attribution — "Manifesto of 19 February 1861" |

Not allowed: the opening of the 1856 speech about "rumours" (out of context it means the opposite); anything found only on quote aggregator sites.

Print sources: «Голос минувшего», 1916, № 5–6, p. 393; Tatishchev S. S., Emperor Alexander II, vol. 1, Moscow, 1996, p. 331; Lyashenko L. M., Alexander II, Moscow, 2002, pp. 170–171 (in Russian).

## Sources

- Alexander II: https://inventaire.io/entity/wd:Q83171
- The 1858 black-gold-white flag: https://cyclowiki.org/wiki/Чёрно-жёлто-белый_флаг
- JFD's Russia: Elisabeth (structural reference): `reference/samples/JFD-Russia-Elisabeth`
