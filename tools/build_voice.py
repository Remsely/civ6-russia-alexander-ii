"""Build the local voice prototype using an external, pinned bnktool (AGPL-3.0-only).

Download instructions and limitations: docs/voice-integration.ru.md.
No game audio is copied into the output; only sound/mixer layout is read locally.
"""
import argparse
import hashlib
import json
import runpy
import struct
import tempfile
import uuid
from pathlib import Path

import numpy as np
import wave
from lxml import etree

from leader_voice import BANK, GAIN_DB, LEADER_SPEECH, LINES, ROOT, SELECTED, STOP, bind_scene, event

TOOL_SHA = '6bde737465b5b06b376af4489cc84e06d591d40f284c62a3f8f92fac9609edad'
GAME_AUDIO = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization VI/Base/Platforms/Windows/audio")
OUT = ROOT / 'mod/Platforms/Windows/Audio'


def save(tree, path):
    tree.write(str(path), encoding='utf-8', xml_declaration=True, pretty_print=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bnktool', type=Path, default=ROOT / 'art/build/voice/integration/bnktool.py')
    parser.add_argument('--game-audio', type=Path, default=GAME_AUDIO)
    args = parser.parse_args()
    if hashlib.sha256(args.bnktool.read_bytes()).hexdigest() != TOOL_SHA:
        raise ValueError('Unexpected bnktool version; review the dependency before using it')
    tool = runpy.run_path(str(args.bnktool))
    fnv = tool['fnv']
    original = (args.game_audio / 'Speech.bnk').read_bytes()
    objects = {struct.unpack_from('<I', body)[0]: (kind, body)
               for kind, body in tool['read_hirc'](original)}
    assert struct.unpack_from('<I', original, 8)[0] == 113
    greeting = objects[fnv(LINES['FIRST_MEET'][1])][1]
    action = objects[struct.unpack_from('<I', greeting, 8)[0]][1]
    sound = bytearray(objects[struct.unpack_from('<I', action, 6)[0]][1])
    # v113 source header: plugin, stream type, source id, prefetch/media size.
    assert len(sound) == 51 and sound[8] == 2
    sound[8] = 0  # fully embedded PCM; no streamed game .wem is used
    chain = tool['official_chain'](str(args.game_audio / 'Speech.bnk'), LINES['FIRST_MEET'][1])
    assert len(chain) == 3
    assert struct.unpack_from('<I', chain[-1], 7)[0] == fnv('Speech Bus')
    # v113 actor-mixer: one property (id 0 = Volume), float dB at offset 18.
    # Adjust only our cloned mixer; PCM and the game's shared speech bus stay intact.
    mixer = bytearray(chain[0])
    assert mixer[16:18] == b'\x01\x00'
    base_db = struct.unpack_from('<f', mixer, 18)[0]
    assert base_db == -8.0
    struct.pack_into('<f', mixer, 18, base_db + GAIN_DB)
    # Keep the shared LeaderSpeech ancestry so native Escape/RMB stop actions
    # reach us. Only our own lower mixer is cloned; no vanilla object is replaced.
    assert tool['mixer_parent'](mixer)[0] == LEADER_SPEECH
    chain = [bytes(mixer)]
    manifest = {x['file']: x for x in json.loads((SELECTED / 'manifest.json').read_text(encoding='utf-8-sig'))}
    voices, report = [], []
    with tempfile.TemporaryDirectory(prefix='alexander-voice-') as temp:
        for slot, (filename, _) in LINES.items():
            source = SELECTED / filename
            if hashlib.sha256(source.read_bytes()).hexdigest() != manifest[filename]['sha256']:
                raise ValueError('Selected recording changed: ' + filename)
            with wave.open(str(source), 'rb') as recording:
                rate = recording.getframerate()
                assert recording.getnchannels() == 1 and recording.getsampwidth() == 3
                raw = np.frombuffer(recording.readframes(recording.getnframes()), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            values = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
            values[values >= 0x800000] -= 0x1000000
            samples = (values / 8388608.0).reshape(-1, 1)
            assert rate == 48000 and samples.shape[1] == 1
            assert np.isfinite(samples).all() and np.max(np.abs(samples)) < 1
            wav = Path(temp) / filename
            with wave.open(str(wav), 'wb') as converted:
                converted.setnchannels(1)
                converted.setsampwidth(2)
                converted.setframerate(rate)
                converted.writeframes(np.clip(np.rint(samples * 32768), -32768, 32767).astype('<i2').tobytes())
            voices.append(dict(event=event(slot), wem=tool['pcm_wem'](str(wav)), body=bytes(sound), plugin=0x00010001))
            report.append(dict(slot=slot, event=event(slot), source=filename, seconds=len(samples) / rate))
    blob, ids = tool['build_bank'](BANK, voices, chain=chain)
    # Our UI stop targets only our own branch. Native Stop_Leader_Speech reaches
    # the same sounds through their shared vanilla LeaderSpeech ancestor.
    stop_event = objects[fnv('Stop_Leader_Speech')][1]
    stop_action = bytearray(objects[struct.unpack_from('<I', stop_event, 8)[0]][1])
    assert stop_action[4:6] == b'\x02\x01'
    assert struct.unpack_from('<I', stop_action, 6)[0] == LEADER_SPEECH
    stop_id = fnv(BANK + '/stop')
    struct.pack_into('<I', stop_action, 0, stop_id)
    struct.pack_into('<I', stop_action, 6, fnv(BANK + '/chain0'))
    built = tool['read_hirc'](blob)
    built.extend([(3, bytes(stop_action)), (4, struct.pack('<III', fnv(STOP), 1, stop_id))])
    media = [(fnv(f'{BANK}/media{i}'), v['wem']) for i, v in enumerate(voices)]
    blob = tool['assemble'](BANK, built, media)
    chunks = {tag: (off, size) for tag, off, size in tool['read_chunks'](blob)}
    assert chunks['DATA'][0] % 16 == 0
    assert len({struct.unpack_from('<I', body)[0] for _, body in built}) == len(built)
    assert not (set(objects) & {struct.unpack_from('<I', body)[0] for _, body in built})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (BANK + '.bnk')).write_bytes(blob)
    (OUT / 'REMSELY_AlexanderIIBanks.ini').write_text(
        '[Global]\n\n[Menu]\n\n[InGame]\n' + BANK + '.bnk\n\n[2D]\n\n[3D]\n\n[FMV]\n', encoding='utf-8')
    meta = etree.Element('SoundBanksInfo', Platform='Windows', BasePlatform='Windows', SchemaVersion='10', SoundbankVersion='113')
    bank = etree.SubElement(etree.SubElement(meta, 'SoundBanks'), 'SoundBank', Id=str(ids['bank']), Language='SFX')
    etree.SubElement(bank, 'ShortName').text = BANK
    etree.SubElement(bank, 'Path').text = BANK + '.bnk'
    events = etree.SubElement(bank, 'IncludedEvents')
    for name in [*(v['event'] for v in voices), STOP]:
        etree.SubElement(events, 'Event', Id=str(fnv(name)), Name=name,
                         GUID='{' + str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper() + '}')
    memory = etree.SubElement(bank, 'IncludedMemoryFiles')
    for i, item in enumerate(report):
        node = etree.SubElement(memory, 'File', Id=str(media[i][0]), Language='SFX')
        etree.SubElement(node, 'ShortName').text = item['source']
        etree.SubElement(node, 'Path').text = str(media[i][0]) + '.wem'
    save(etree.ElementTree(meta), OUT / (BANK + '.xml'))
    scene = ROOT / 'mod/Assets/AlexanderII.ast'
    tree = etree.parse(str(scene))
    bind_scene(tree)
    save(tree, scene)
    # Register audio and the small, independent UI context (no vanilla UI override).
    modinfo = ROOT / 'mod/RemselysAlexanderII.modinfo'
    tree = etree.parse(str(modinfo))
    files = ['Platforms/Windows/Audio/' + name for name in
             ['REMSELY_AlexanderIIBanks.ini', BANK + '.bnk', BANK + '.xml']]
    actions = tree.find('InGameActions')
    existing = actions.find("UpdateAudio[@id='REMSELY_InGame_Audio']")
    if existing is not None:
        actions.remove(existing)
    audio = etree.SubElement(actions, 'UpdateAudio', id='REMSELY_InGame_Audio')
    for rel in files:
        etree.SubElement(audio, 'File').text = rel
    if actions.find("AddUserInterfaces[@id='REMSELY_Voice_UI']") is None:
        ui = etree.SubElement(actions, 'AddUserInterfaces', id='REMSELY_Voice_UI')
        etree.SubElement(etree.SubElement(ui, 'Properties'), 'Context').text = 'InGame'
        etree.SubElement(ui, 'File').text = 'UI/RemselysAlexanderII_Voice.xml'
    files += ['UI/RemselysAlexanderII_Voice.xml', 'UI/RemselysAlexanderII_Voice.lua']
    listed = {node.text for node in tree.findall('./Files/File')}
    for rel in files:
        if rel not in listed:
            etree.SubElement(tree.find('Files'), 'File').text = rel
    etree.indent(tree, space='  ')
    save(tree, modinfo)
    report_path = ROOT / 'art/build/voice/integration/build-report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(dict(bank=ids['bank'], gain_db=GAIN_DB, sha256=hashlib.sha256(blob).hexdigest(), lines=report), indent=2), encoding='utf-8')
    for item in report:
        print(f"{item['slot']}: {item['seconds']:.2f}s -> {item['event']}")
    print(f'Built {len(blob):,} bytes; v113; speech bus; own stop event. Build does not test in-game playback.')


if __name__ == '__main__':
    main()
