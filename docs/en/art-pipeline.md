# Art Pipeline (2D and 3D)

Russian version: [`../ru/art-pipeline.md`](../ru/art-pipeline.md). Image generation prompts and services: `art/prompts.md`. Screen pitfalls and texture names: the `civ6-leader-art` skill; 3D pipeline details: the `civ6-asset-pipeline` skill.

## 2D leader art

Sources: `art/source/alexander_ii_full.png` (full height, transparent background) and `alexander_ii_short.png` (waist up, transparent background).

1. `tools/slice_art.py` — from the sources into `art/build/`: an 827x1024 portrait (from the full-height one, framed to the hips) and round icons 256/80/64/55/50/48/45/32 (from the waist-up one).
2. `tools/make_art.py` — from `art/build/` into `mod/`:
   - `Textures/*.dds` + `*.tex` (uncompressed RGBA, the JFD Elisabeth format; the fallback has 11 mip levels);
   - `XLPs/Icons.xlp` (icons and portrait), `XLPs/LeaderFallbacks.xlp`;
   - `ArtDefs/{FallbackLeaders,Leaders,UserInterface}.artdef`;
   - `RemselysAlexanderII.dep`;
   - `Data/Icons.sql` (the `ICON_ATLAS_REMSELY_ALEXANDER_II` atlas, the `ICON_LEADER_REMSELY_ALEXANDER_II` icon).

Names: portrait `LEADER_REMSELY_ALEXANDER_II_NEUTRAL`, fallback `FALLBACK_NEUTRAL_REMSELY_ALEXANDER_II`, icons `RemselysAlexanderII_Icon<size>`.

`.blp` is cooked by the SDK cooker: `tools/build.py` (same as ModBuddy cooking, without ModBuddy). Without BLPs the portrait (setup and loading screens) and the fallback (diplomacy) do not work. The leader icon loads straight from `.dds` via `Data/Icons.sql` and works without BLPs. Required outputs: `Platforms/{Windows,MacOS}/BLPs/UI/Icons.blp` and `LeaderFallbacks.blp`.

Structural reference: `reference/samples/JFD-Russia-Elisabeth`.

## 3D leader

The diplomacy backdrop behind the 3D model is not an asset but the UI (`LeaderScene.lua` lays the background texture under the model; without it the screen is black). The background texture goes through the shared 2D pipeline (`slice_art.py` → `make_art.py`).

The pipeline (all commands in `CLAUDE.md`, "Команды"):

1. **Model build** — the historical `art/3d/build_all.py` pipeline builds from source scripts (do not run blindly on the accepted model): the portrait pose, cloth, regalia, orders, bones of hanging parts, motion weights; the result is `art/3d/alexander_leader.blend`. Texture edits without rebuilding geometry: the separate scripts `build_<regalia|orders|details>.py`, `build_orders.py -- orders`, `uniform_paint.py`, `head_touchup.py` and others (same folder).
2. **Checks** — `tools/blend.py audit|render|clash|stress` (headless Blender 4.5): mesh and weight numbers, frames from the leader camera, object interpenetration, motion stress tests. Run after every step.
3. **FBX export** — `art/3d/export_leader.py -- geometry` and `-- animation` (geometry in rest pose, triangulated, ≤4 bones per vertex, triangle group = material `LEAD_REMSELY_ALEXANDER_II_<part>`; the `idle` loop at 30 fps).
4. **Asset assembly** — `art/3d/make_leader_asset.py`: `.fgx` via `tools/fbx_to_fgx.ps1`, `.geo`, `AlexanderII_Idle.anm`, Leader-class materials, BaseColor/Normal/Metalness/Gloss/AO textures into `mod/Textures`, `.ast`.
5. **Wiring** — `tools/make_leader3d.py` (XLP, `Leader_BLP_Entry`, the `.dep` package, files in `.modinfo`; run after `make_art.py`, then `make_modbuddy.py`), then `tools/build.py` (the leader BLP).

The scripts generate `.geo`, `.anm` and `.ast` without Asset Editor; `tools/build.py` checks the cooked bone palettes before installation. The asset uses the vanilla Peter camera. See [3D import history](../3d-game-import.md) for the verified pipeline. Do not blindly rebuild the accepted head: `build_head.py` is not reproducible.
