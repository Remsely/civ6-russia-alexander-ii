"""Measure first-meeting speech files and static Wwise volume, not live game output.
Uses the pinned local bnktool, vgmstream and ffmpeg; writes ignored diagnostic files.
"""
import json
import hashlib
import re
import runpy
import struct
import subprocess
from pathlib import Path
import imageio_ffmpeg
from leader_voice import ROOT

GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization VI")
OUT = ROOT / 'art/build/voice/integration/levels'
CASES = {
    'Peter': 'Play_RUSS_PA_FIRST_MEET_J_Edited',
    'Cleopatra': 'EGYP_CP_FIRST_MEET_A_4NewEdit2',
    'Gilgamesh': 'SUME_GL_FIRST_MEET_F_new',
    'Teddy': 'Leader_AMER_TR_FIRST_MEET_B_04',
    'Mansa Musa': 'MANSAMUSA_01_FirstMeet_VO_FX',
    'Kupe': 'KUPE_01_FirstMeet_VO_FX',
    'Kristina': 'KRISTINA_01_FirstMeet_VO_FX',
    'Pachacuti': 'PACHACUTI_01_FirstMeet_VO_FX',
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    from build_voice import TOOL_SHA
    tool_path = ROOT / 'art/build/voice/integration/bnktool.py'
    assert hashlib.sha256(tool_path.read_bytes()).hexdigest() == TOOL_SHA
    tool = runpy.run_path(str(tool_path))
    objects = {}
    voice_media = set()
    listing = GAME / 'DLC/Expansion2/Platforms/Windows/audio/XP2_Leader_SFX.txt'
    for line in listing.read_text(encoding='utf-16').splitlines():
        fields = line.strip().split('\t')
        if len(fields) > 1 and fields[0].isdigit() and fields[1].startswith('VO_'):
            voice_media.add(int(fields[0]))
    banks = [GAME / 'Base/Platforms/Windows/audio/Speech.bnk',
             GAME / 'DLC/Expansion2/Platforms/Windows/audio/XP2_Leader_SFX.bnk']
    for path in banks:
        for kind, body in tool['read_hirc'](path.read_bytes()):
            objects[struct.unpack_from('<I', body)[0]] = (kind, body, path)

    def volume(body, position):
        count = body[position]
        ids = body[position+1:position+1+count]
        values = struct.unpack_from('<' + 'f'*count, body, position+1+count)
        return dict(zip(ids, values)).get(0, 0.0)

    def gain(key):
        total, chain = 0.0, []
        while key in objects:
            kind, body, _ = objects[key]
            assert kind in (2, 7)
            v = volume(body, 30 if kind == 2 else 16)
            total += v
            chain.append(dict(id=key, kind=kind, volume_db=v))
            key = struct.unpack_from('<I', body, 25)[0] if kind == 2 else tool['mixer_parent'](body)[0]
            if kind == 7 and struct.unpack_from('<I', body, 7)[0]:
                break  # stop at output bus (shared game/user controls excluded)
        return total, chain

    def measure(path):
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-i', str(path),
                                 '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                                check=True, capture_output=True, text=True)
        summary = result.stderr.rsplit('Summary:', 1)[1]
        return dict(lufs=float(re.search(r'I:\s+(-?[\d.]+) LUFS', summary)[1]),
                    true_peak_dbfs=float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', summary)[1]))

    report = []
    for leader, name in CASES.items():
        _, event, _ = objects[tool['fnv'](name)]
        actions = struct.unpack_from('<'+'I'*struct.unpack_from('<I',event,4)[0],event,8)
        candidates = []
        for action in actions:
            _, action, _ = objects[action]
            key = struct.unpack_from('<I',action,6)[0]
            kind, body, bank = objects[key]
            assert kind == 2
            media = struct.unpack_from('<I',body,9)[0]
            # Expansion events play cloth/foley and VO together; measure VO only.
            if name.endswith('_VO_FX') and media not in voice_media:
                continue
            candidates.append((key, media, bank))
        assert len(candidates) == 1
        key, media, bank = candidates[0]
        source = bank.parent / (str(media)+'.wem')
        assert source.is_file(), source
        decoded = OUT / (leader.replace(' ', '-')+'.wav')
        subprocess.run([str(ROOT/'art/build/voice/vgmstream/bin/vgmstream-cli.exe'),
                        '-o',str(decoded),str(source)],check=True,capture_output=True)
        static_gain, chain = gain(key)
        levels = measure(decoded)
        report.append(dict(leader=leader,event=name,media=media,**levels,
                           static_gain_db=static_gain, chain=chain,
                           estimated_lufs_before_shared_bus=levels['lufs']+static_gain))
    levels = measure(ROOT/'art/voice/selected/first-meet-clean.wav')
    # Installed original clone uses Peter's complete routing and static gain.
    peter = next(r for r in report if r['leader']=='Peter')
    report.append(dict(leader='Alexander II (before boost)',**levels,
                       static_gain_db=peter['static_gain_db'],
                       estimated_lufs_before_shared_bus=levels['lufs']+peter['static_gain_db']))
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in report:
        print(r['leader'],r['lufs'],r['static_gain_db'],r['estimated_lufs_before_shared_bus'])


if __name__ == '__main__':
    main()
