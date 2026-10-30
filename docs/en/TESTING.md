# In-Game Testing

The player performs the in-game checks. Building and installation can be scripted; do not launch the game from the agent. Russian version: [`../ru/TESTING.md`](../ru/TESTING.md).

## Preparation

1. `.venv\Scripts\python.exe tools\install.py` (validate + copy to `Documents\My Games\Sid Meier's Civilization VI\Mods`).
2. **Restart the game** and enable the mod in "Additional Content" → "Mods". Rise and Fall is required; the Future Era needs Gathering Storm.
3. Start a **new** game as Russia: colors and city lists are stored in the save; art-only changes can be checked in an existing game after restarting.

Speed-up: FireTuner — grant techs, change era, assign a Governor.

## Screens

- [ ] Leader setup: Alexander II among Russia's leaders, portrait and icon in place, black-and-gold border.
- [ ] Loading: background, portrait and the leader paragraph.
- [ ] Diplomacy: the **3D leader** in place (no black screen), the hall background behind it, the idle loop (looks at the camera, breathes, blinks, steps), lines, the Liberator agenda in the list.
- [ ] Civilopedia: the leader page with description and history.

## Mechanics

- [ ] Builders start with +1 charge.
- [ ] Pastures +1 Production.
- [ ] A Farm with 2 adjacent Farms gives +1 **Food**, with 4 — +2 (Food icon in the plot tooltip).
- [ ] Zemstvos: a city with an assigned Governor gets +2 Culture and +4 Loyalty; values grow from the Medieval Era per the table in the [design doc](design.md).
- [ ] Unit upgrades are 50% cheaper.
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
