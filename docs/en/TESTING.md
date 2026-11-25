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
- [ ] With AI Alexander, verify +3 for a shared religion and −12 for conversion of his own city. Check the displayed reasons, the separate standard conversion modifier and behavior without a founded religion. Repeat a conversion and confirm that no custom accumulating penalty appears.
- [ ] Observe which religion AI Alexander founds when Eastern Orthodoxy is available. When Holy War is available, record the casus belli the AI uses if it declares one. These settings are preferences.

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

The player has confirmed basic diplomacy playback, the line when concluding a trade deal, loading narration and a restart from the pause menu. Use the latest Windows build for the remaining checks. The player launches the game.

- [ ] First meeting, both war directions and agenda approval/warning: one playback, timely transition to responses, Escape/RMB during speech, leader switching and the speech-volume control.
- [ ] Both defeat texts: the recording matches the subtitles, the two voices never overlap and neither ending is cut off. Lua.log markers: `REMSELY voice: defeat variant FROM_AI` / `FROM_HUMAN`.
- [ ] Other 24 dialogue lines: correct recordings for delegations, friendship, deals, borders and peace; opening the scene does not immediately stop them.
- [ ] Extended voice routes: sample a statement, an agenda reason and a deal-interface line. Compare timing and audio to the English and Russian subtitles. Check that “Goodbye”, Escape and right-click stop a playing line, while a follow-up response can finish after an automatic close. The 137 additional routes have not all been verified.
- [ ] Trade: change a resource amount several times, leave the screen and conclude a deal. Check that voice does not replay on quantity changes, and that subtitles and the deal conclusion line work. Test the standard UI and the UI mod setup independently.
- [ ] Test Russian and English loading narration at the in-game volume. For a new game, a second game in the same session, a restart and a saved game, check that the era introduction is followed by the selected narrator and that entering the game stops playback. Include a later era.
- [ ] In both Russian and English interfaces, Alexander speaks Russian and subtitles follow the interface language.

Quality review by number: [catalog](../voice-review.ru.md); build, limitations and current routes: [integration](../voice-integration.ru.md) (Russian). A recording's presence in the bank does not complete a listening check.
