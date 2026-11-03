# In-Game Testing

The player performs the in-game checks. Building and installation can be scripted; do not launch the game from the agent. Russian version: [`../ru/TESTING.md`](../ru/TESTING.md).

## Preparation

1. `.venv\Scripts\python.exe tools\install.py` (validate + copy to `Documents\My Games\Sid Meier's Civilization VI\Mods`).
2. **Restart the game** and enable the mod in "Additional Content" → "Mods". Gathering Storm is required (railroads, Governors).
3. Start a **new** game as Russia: colors and city lists are stored in the save; art-only changes can be checked in an existing game after restarting.

Speed-up: FireTuner — grant techs, change era, assign a Governor.

## Screens

- [ ] Leader setup: Alexander II among Russia's leaders, portrait and icon in place, black-and-gold border.
- [ ] Loading: background, portrait and the leader paragraph.
- [ ] Diplomacy: the **3D leader** in place (no black screen), the hall background behind it, the idle loop (looks at the camera, breathes, blinks, steps), lines, the Liberator agenda in the list.
- [ ] Civilopedia: the leader page with description and history.

## Mechanics

- [ ] Before the Industrial Era the ability gives nothing: Builders have normal charges; Farms and Pastures are vanilla, unit upgrades at full price.
- [ ] From the Industrial Era: Builders get +1 charge. The Farm adjacency bonus is gone in every era (removed on 3 November 2026).
- [ ] **Governor title**: on entering the Industrial Era the title counter increases by 1 (vanilla grants titles only from built things — this is our new combination, check it right on the era boundary).
- [ ] Zemstvos: a city with an assigned Governor grows 10% faster; cities without a Governor do not.
- [ ] Railway Network: every city gets +1 Production per other city of your civilization and +1 Gold per foreign city (city-states and civs at war count) connected to it by a continuous railroad; a rail on the city center tile itself is not required — the center touching a railroad plot is enough; foreign rails count as transit, a line may pass through a city junction; the Capital is an ordinary city and bonuses like any other; two own cities linked by rails not through the Capital still bonus each other.
- [ ] Population cap on both bonuses: a city with Population N gets at most +N Production and at most +N Gold from railroads each (e.g. Pop 10 with 15 connected own and 20 foreign cities gives +10 and +10, not +15/+20); population growth raises both caps immediately.
- [ ] Railroads: bonuses appear right after a segment is built (route events); a captured city or a moved capital is picked up by the next turn. The Military Engineer unlocks railroads after Steam Power (1 Iron + 1 Coal per tile).
- [ ] The old Zemstvos are gone: no Culture or Loyalty in Governor cities.
- [ ] AI Alexander plays without errors, the agenda fires (likes peaceful, dislikes recent aggressors).

## Cities

- [ ] The first city is Saint Petersburg; then in order: Moscow, Nizhny Novgorod, Kazan, Odessa, Kharkov, Sevastopol, Vladivostok, Khabarovsk, Blagoveshchensk, Tashkent, Verny, Novorossiysk, Rostov-on-Don, Baku, Riga, Novo-Arkhangelsk, Yekaterinburg, Irkutsk, Omsk, Tomsk — then the vanilla reserve (Novgorod, Astrakhan, …).
- [ ] A game as Peter the Great: his city list unchanged (the same vanilla queue).

## 3D leader (when art changed)

- [ ] Close-ups against the portrait: face, orders, the buckle, the neck cross.
- [ ] Motion without mesh breaks: blinking, head turn, the step (see `tools/blend.py stress` in `CLAUDE.md`).

## General

- [ ] Saving and loading a game.
- [ ] Russian and English interface (switch the game language).
- [ ] The mod alongside BBG and BBM: loads without errors, bonuses don't double.

## Logs

`%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\`: `Database.log`, `Modding.log`, `Lua.log`, `ArtDef.log` (3D and art). Look for lines with `ERROR` and `Remsely`/`REMSELY`. `tools/validate.py` does not catch everything: for example, a bad `PlayerColors` column only shows in `Database.log` (look for `[ColorManager] ERROR`).


## Voice confirmation and regression checks

On November 1, 2026, the user confirmed the earlier Windows build with six diplomacy recordings after loop, duration and Escape fixes. That confirmation does not cover the later expansion. All 31 diplomacy texts and Russian loading narration are now integrated; new routing needs testing after a game restart. The user launches the game.

- [ ] First meeting, both war directions and agenda approval/warning: one playback, timely transition to responses, Escape/RMB during speech, leader switching and the speech-volume control.
- [ ] Both defeat texts: the recording matches the subtitles, the two voices never overlap and neither ending is cut off. Lua.log markers: `REMSELY voice: defeat variant FROM_AI` / `FROM_HUMAN`.
- [ ] Other 24 dialogue lines: correct recordings for delegations, friendship, deals, borders and peace; opening the scene does not immediately stop them.
- [ ] Russian loading narration: full text, measured delivery, volume comparable to other loading narrators, no loops, and stops when loading closes. Marker: `REMSELY voice: loading narration started`.
- [ ] In both Russian and English interfaces, Alexander speaks Russian and subtitles follow the interface language.
- [ ] Once an English narrator is integrated: only loading narration follows the interface language; diplomacy remains Russian. English audio is currently absent, so both interfaces temporarily use RU loading narration.

Quality review by number: [catalog](../voice-review.ru.md); build, limitations and current routes: [integration](../voice-integration.ru.md) (Russian). A recording's presence in the bank does not complete a listening check.
