# Ideas Bank — Remsely's Alexander II

Future ideas, **not in the current release**. Chosen items move to [`../../ROADMAP.md`](../../ROADMAP.md). The Russian file is the source of truth: [`../ru/ideas.md`](../ru/ideas.md).

## Agreed direction — 31 October 2026

These decisions supersede conflicting earlier proposals below; implementation and balance still need testing.

- Railways: first test the user's mechanic: +1 Production per connected city of the player's civilization and +2 Gold per connected city of another civilization. Define connection and ownership rules before implementation; no cap has been agreed.
- Emancipation: from the Industrial Era, +1 Builder charge and +1 Food per two adjacent Farms, without an artificial +2 cap. Remove Pasture Production and the unit upgrade discount. Investigate effects on existing Builders.
- Starting locations: experiment with tundra, rivers and coast on generated maps; consider true-start maps, the effect on Peter and compatibility separately.
- Unique district and building: financial theme and State Bank; devise original mechanics closer to implementation, and confirm the district in light of its design.
- Voice: high quality, including research into AI and local options; loading narration in English and Russian, diplomacy in Russian.
- Additional diplomatic animations; investigate mouth movement timed to speech.
- Unique unit: a Berdan rifleman candidate; bonuses undecided.
- Natural wonder: Lena Pillars selected; mechanics undecided.
- City-state: the free cities Frankfurt am Main and Lübeck are candidates; choose between them and design mechanics during implementation. Both are on Germany’s in-game city list: test duplicate names and compatibility with installed mods.

## Implementation principles (binding for every idea)

1. **Extend, never replace**: own rows (`INSERT`) and own files only; `UPDATE`/`DELETE` of vanilla rows and replacing engine files are forbidden. Replacing a building/district via `BuildingReplaces`/`DistrictReplaces` and disabling a district via `ExcludedDistricts` are official extension mechanisms, not violations.
2. **Everything ours under `REMSELY_`**: types, traits, modifiers, plot properties, scripts. Foreign types (vanilla, BBG, BBM) are never edited and never assumed present.
3. **Independence**: without BBG/BBM the mod is fully correct; with them it coexists without depending on load order. If BBG rebalances something we replaced (the Bank, the Lavra), our replacement keeps its own numbers — that is how the official mechanism works, not a breakage; record it in the test plan.
4. **What cannot be expressed additively is not done**, or is moved to our own ground (own map scripts, like start-bias variant C).

## Earlier research and alternatives

The sections below are retained for context and may conflict with the decisions above; they are not an approved specification.

## Emancipation rebalance — Industrial Era threshold

User's idea: all three "Emancipation of the Serfs" bonuses — Builder +1 charge, Pasture +1 Production, Farm +1 Food per 2 neighbours — apply only from the Industrial Era (today they work all game, too strong in the early game). Historically apt: the reforms belong to the second half of the 19th century.

- Implementation: add an "era not earlier than Industrial" requirement to the three modifiers (`REMSELY_REFORMS_BUILDER_CHARGES`, `REMSELY_REFORMS_PASTURE_PRODUCTION`, `REMSELY_REFORMS_FARM_ADJ_2/_4_FOOD`) — the same era-threshold mechanism the Zemstvos use.
- Design caveat: before the Industrial Era only the Zemstvos and the upgrade discount remain — half a game with almost no ability. Possibly intentional (a peaceful late game), but check how it feels.

## Start bias — "Petersburg, not tundra"

User's idea: add "river + coast" bias rows for Russia (Petersburg). By the extend-only principle the vanilla tundra bias cannot be weakened (`UPDATE` forbidden) — tundra tier 1 stays; river and coast are added on top; if that proves too weak — variant C (own maps).

- Mechanics (verified in the game DB): biases live in `StartBiasTerrains` / `StartBiasRivers` / `StartBiasNegatives` / `StartBiasCustom` with tiers 1–5 (1 strongest). "River by the coast" is two rows: `StartBiasRivers` + `StartBiasTerrains (TERRAIN_COAST)` — together they produce an estuary; coast tier 1 is used by England, Japan, Spain. No major civilization uses river tier 1 in vanilla (strongest: Netherlands, tier 2). Russia has tundra and tundra-hills tier 1 — untouched (INSERT-only principle).
- Limitation: bias tables have no `LeaderType` — the bias changes for all of Russia: Peter also leaves the tundra, and his Mother Russia and Lavra are tuned for tundra. A conscious trade-off.
- "Only when BBG is loaded": BBG has no bias system of its own (only balance tables like `WonderTerrainFeature_BBG` in the cache). Conditional insert via an SQL trick: `INSERT INTO … SELECT … WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE name='WonderTerrainFeature_BBG')`; verify in game that the game's SQLite accepts a subquery to sqlite_master.

Per-leader bias (research of 2026-10-25): the only leader-level hook in start data is the `MapStartPositions` table of the configuration database (true-start Earth maps); its rows are (map, plot, `'LEADER'`, leader). Peter stands on plot 7222 in `TSLWorldMapHuge` and `TSLWorldMapHuge_XP2` — Saint Petersburg; inserting two rows with `LEADER_REMSELY_ALEXANDER_II` gives Alexander a true start in Petersburg on Earth maps (no clash with Peter — there is one Russia per game). Written by the same action as our `Config.sql` (UpdateDatabase in FrontEnd, configuration database).

**Generated maps — the matrix for "extend only, guarantee correct behavior in vanilla, with BBG and with BBM"** (an earlier plan to shadow the base `AssignStartingPlots.lua` with a 2291-line copy was rejected: it replaces an engine file and is conflict-prone):

- **A. Earth maps (TSL)** — two rows in `MapStartPositions` (Petersburg, Peter's plot 7222). Purely additive, leader-level, identical in vanilla, with BBG and with BBM (BBM does not replace Earth maps).
- **B. Generated maps, civilization-level** — `INSERT OR IGNORE` of new Russia bias rows (`StartBiasRivers` T1/T2 + `StartBiasTerrains` `TERRAIN_COAST` T1/T2), no UPDATE of vanilla rows. Works in all three configurations: the vanilla engine reads these tables during placement, and BBS (BBM's maps) reads them itself via `GameInfo.StartBias*`; BBG edits existing rows with UPDATEs and does not conflict with our INSERTs. The cost: it affects all of Russia, Peter included.
- **C. Generated maps, leader-level (optional, if B is not enough)** — our own map scripts in the mod ("Continents — Remsely's Russia" etc.), self-contained: base generation + a leader-level post-pass (`PlayerConfigurations:GetLeaderTypeName`, `Players:SetStartingPlot`). Nothing base is replaced; guaranteed behavior in any configuration; the cost — it only works when our map is chosen.

## State Bank — unique building replacing the Bank

The State Bank was founded in 1860 and financed the reforms and the railways. Attached via a leader trait (precedent: Eleanor's Queen's Bibliothèque, `TRAIT_LEADER_BUILDING_QUEENS_BIBLIOTHEQUE`; scheme: `Buildings.TraitType` + `BuildingReplaces`, like Japan's Electronics Factory replacing the Factory).

Game mechanics (draft): keeps the Bank's bonuses and adds — in this city districts can be bought with Gold (`MODIFIER_CITY_ADJUST_CAN_PURCHASE_DISTRICTS`) at a 20% discount (`MODIFIER_SINGLE_CITY_ADJUST_ALL_DISTRICTS_PURCHASE_COST`). A credit mechanic: buying now costs more than building, but is instant.

## Railway reform — part of the ability (not a district)

A city gets +1 Production for every city of its own civilization connected to it by rail, and +1 Gold for every connected foreign city. Connection = an unbroken path of railroad tiles (`ROUTE_RAILROAD`) between city centers.

- Requires Gathering Storm (railroads arrive with the Steel tech, built by a Military Engineer); with R&F only the bonus simply never fires — document it.
- Implementation: Lua computes connectivity (search from city centers over railroad tiles) and sets counter properties on the city-center plot; read via thresholds with `REQUIREMENT_PLOT_PROPERTY_MATCHES` + `MODIFIER_PLAYER_ADJUST_PLOT_YIELD` — an extension of the farm pattern. There is no event for road changes — recompute once per turn.
- Balance in question: late game 15 cities give every city +14 Production (half a wonder). Gentler option: +1 Production per 2 connected own cities, +1 Gold per foreign city.

Historical note (verified 2026-10-25): the network grew from ~920 km (1855) to ~22,900 km (1880) — 25-fold, faster than every great power (Germany ×2.9, USA ×3, Britain ×1.6 over 1860–1880); by 1880 Russia caught up with Britain and France in network length. The program was Alexander II's 1857 rescript (the Main Society of Russian Railways, foreign capital, state guarantees), private concessions from 1867. There was no aggregate industrial leap (that came in the 1890s, Witte), but the foundation was laid: Donbass and Yuzovka (1869), Baku oil (1872), railway-driven machine building, the State Bank of 1860. Source: [History of rail transport in Russia — Wikipedia](https://en.wikipedia.org/wiki/History_of_rail_transport_in_Russia).

## Alexander's unique district instead of the Lavra

Disabling the Lavra for one leader — the Mvemba pattern (Kongo cannot build Holy Sites): `ExcludedDistricts (DISTRICT_LAVRA, <Alexander's trait>)`. Our district: `Districts.TraitType` + `DistrictReplaces → DISTRICT_HOLY_SITE`. Verify in game: the exclusion works on a unique (not base) district; that Alexander sees his district, not the plain Holy Site; that Peter is unchanged. Fallback: the district replaces the Lavra itself (`DistrictReplaces`; a unique district can replace only one district — primary key).

District ideas as they would read in game:

| District | Replaces | Bonus | Historical justification |
|---|---|---|---|
| Russian-American Factory | Harbor | +1 Gold per adjacent sea resource; on completion the city gains +200 Gold (the Alaska sale) | Russian-American Company: fur trade on the Pacific; Novo-Arkhangelsk, capital of Russian America, is in the city list; Alaska sold in 1867 for $7.2M |
| Railway Station | Commercial Hub | +1 Gold per other city of yours with a Station; domestic trade routes from the city +2 Food and +2 Production | The era's railway boom: ~1,000 km of track in 1855 to ~22,000 by the end of the reign; the Orenburg and Transcaspian lines; the reign's great build — rails tied the empire together and the network paid for itself |
| Imperial University | Campus | +1 Science per 2 adjacent Farms; +1 Science per era from the Medieval; +2 Great Scientist points in the city | University Charter of 1863 (autonomy); the Bestuzhev Courses of 1878 — the world's first state higher education for women; Tomsk University 1878, first in Siberia; zemstvo agronomy (experimental fields) — the Farm link |
| Palace of Justice | Diplomatic Quarter | +1 Loyalty per adjacent district; enemy spies in the city operate one level weaker | Judicial reform of 1864: jury trials, irremovable judges, open process, justices of the peace — order as the base of loyalty |
| Workers' Quarter | Neighborhood (already replaced by Kongo's Mbanza) | +2 Housing, +1 more per adjacent mine or quarry (instead of Appeal-based housing) | Industrial growth and factory villages: Ivanovo, "the Russian Manchester"; the first factory law of 1866; workers settled by the plants and mines |
| City Duma | Theater Square | +1 Culture and +2 Loyalty per adjacent district | City Statute of 1870: elected city dumas and boards — self-government and urban culture |
| Military District | Encampment | +25% military unit Production in the city | Military districts 1862–64; universal conscription in 1874 (replacing recruit levies); the army's rearmament |

Common to any district: an icon, texts in both languages, 3D art (cheapest is reusing the vanilla asset); non-standard mechanics counted in Lua after the farm-script pattern.
