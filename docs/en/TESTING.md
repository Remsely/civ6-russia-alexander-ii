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

- [ ] Before the Industrial Era the ability gives nothing: Builders have normal charges, Farms give no adjacency Food, Pastures no +1 Production, unit upgrades at full price.
- [ ] From the Industrial Era: Builders get +1 charge; a Farm with 2 adjacent Farms gives +1 **Food**, with 4 — +2, with 6 — +3 (Food icon in the plot tooltip).
- [ ] **Governor title**: on entering the Industrial Era the title counter increases by 1 (vanilla grants titles only from built things — this is our new combination, check it right on the era boundary).
- [ ] Zemstvo Reform: a city with an assigned Governor grows 10% faster; cities without a Governor do not.
- [ ] Railway Network: a city linked to the Capital by a continuous railroad (foreign rails count as transit) gets +1 Production; every connected own city gets +1 Gold per foreign connected city (city-states and civs at war count, no cap); the Capital never bonuses itself.
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
