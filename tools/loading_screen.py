"""Embed the narrator extension so every fresh LoadScreen context gets its code.

FrontEnd module imports may be unavailable after returning from a game to the
menu. Keep editable modules as sources, but do not require runtime include().
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'mod/UI/LoadScreen.lua'


def build_source():
    vanilla = (ROOT / 'reference/vanilla/Base/UI/FrontEnd/LoadScreen.lua').read_text(encoding='utf-8-sig')
    anchor = '\t\tif bPlayDOM then'
    assert vanilla.count(anchor) == 1, 'native dawn audio gate changed'
    vanilla = vanilla.replace(anchor,
        '\t\t-- Alexander dawn audio is driven by our embedded extension.\n'
        '\t\tif leaderType == "LEADER_REMSELY_ALEXANDER_II" then bPlayDOM = false; end\n\n' + anchor)
    module = (ROOT / 'mod/UI/RemselysAlexanderII_LoadScreen.lua').read_text(encoding='utf-8-sig')
    duration_include = 'include("RemselysAlexanderII_LoadingEraDurations");'
    assert module.count(duration_include) == 1
    module = module.replace(duration_include, '-- Era durations are embedded above this module.')
    durations = (ROOT / 'mod/UI/RemselysAlexanderII_LoadingEraDurations.lua').read_text(encoding='utf-8-sig')
    return (vanilla.rstrip() + '\n\n-- BEGIN GENERATED REMSELY LOADING VOICE (tools/loading_screen.py)\n'
            + durations.rstrip() + '\n\n' + module.rstrip()
            + '\nREMSELY_InitializeLoadingVoice();\n-- END GENERATED REMSELY LOADING VOICE\n')


def write_screen():
    OUT.write_text(build_source(), encoding='utf-8')


if __name__ == '__main__':
    write_screen()
    print('LoadScreen generated with embedded voice code and era durations')
