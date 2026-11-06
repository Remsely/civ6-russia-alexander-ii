"""Validate v113 voice bank links, media and scene bindings without Wwise."""
import struct
import json
import hashlib
import wave
import numpy as np
from lxml import etree
from leader_voice import DEFEAT_GROUP, DEFEAT_VALUES, DEFEAT_SWITCH, BANK, GAIN_DB, LEADER_SPEECH, LINES, ROOT, STOP, event, scene_duration


def voice_hash(name):
    result = 2166136261
    for value in name.lower().encode('utf-8'):
        result = ((result * 16777619) & 0xffffffff) ^ value
    return result


def verify_voice():
    path = ROOT / 'mod/Platforms/Windows/Audio' / (BANK + '.bnk')
    data = path.read_bytes()
    chunks = {}
    position = 0
    while position < len(data):
        tag, size = struct.unpack_from('<4sI', data, position)
        end = position + 8 + size
        assert end <= len(data), 'truncated bank chunk'
        chunks[tag] = (position + 8, data[position + 8:end])
        position = end
    assert struct.unpack_from('<II', chunks[b'BKHD'][1]) == (113, voice_hash(BANK))
    assert chunks[b'DATA'][0] % 16 == 0, 'unaligned media'
    media = list(struct.iter_unpack('<III', chunks[b'DIDX'][1]))
    trial = json.loads((ROOT / 'art/voice/game-trial-manifest.json').read_text(encoding='utf-8'))
    selected = {row['file']: row for row in json.loads((ROOT / 'art/voice/selected/manifest.json').read_text(encoding='utf-8-sig'))}
    sources = {slot: dict(file='art/voice/selected/' + filename, sha256=selected[filename]['sha256'])
               for slot, (filename, _) in LINES.items()}
    extras = [row['key'] for row in trial]
    assert len(set(extras)) == len(extras) and not set(extras) & set(LINES), 'duplicate voice slot'
    sources.update({row['key']: row for row in trial})
    texts = {r.get('Tag'): r.findtext('Text') for r in etree.parse(str(ROOT / 'mod/Text/ru_RU.xml')).findall('.//Replace')}
    for row in trial:
        text = texts['LOC_DIPLO_' + row['key'] + '_LEADER_REMSELY_ALEXANDER_II_ANY'].replace(' (Осуждает вас)', '')
        assert text == row['text'], 'voice/subtitle mismatch: ' + row['key']
    from loading_voice import verify_loading_voice
    verify_loading_voice()
    assert len(media) == len(LINES) + len(extras) and media == sorted(media), 'media index'
    for _, start, size in media:
        wem = chunks[b'DATA'][1][start:start + size]
        assert len(wem) == size and wem[:4] == b'RIFF' and wem[8:12] == b'WAVE'
    hirc = chunks[b'HIRC'][1]
    count = struct.unpack_from('<I', hirc)[0]
    objects = {}
    order = []
    position = 4
    for _ in range(count):
        kind, size = struct.unpack_from('<BI', hirc, position)
        body = hirc[position + 5:position + 5 + size]
        assert len(body) == size
        key = struct.unpack_from('<I', body)[0]
        assert key not in objects, 'duplicate object id'
        objects[key] = (kind, body)
        order.append(key)
        position += 5 + size
    assert position == len(hirc)
    kind, container = objects[voice_hash(DEFEAT_SWITCH)]
    assert kind == 6 and struct.unpack_from('<I', container, 11)[0] == voice_hash(BANK + '/chain0')
    group_pos = container.index(struct.pack('<I', voice_hash(DEFEAT_GROUP)))
    cursor = group_pos + 4
    assert struct.unpack_from('<I', container, cursor)[0] == voice_hash(DEFEAT_VALUES[0]), 'defeat default'
    cursor += 4
    assert container[cursor] == 0, 'defeat must not change during playback'
    cursor += 1
    count = struct.unpack_from('<I', container, cursor)[0]
    assert count == 2
    cursor += 4
    defeat_children = list(struct.unpack_from('<II', container, cursor))
    cursor += 8
    assert len(set(defeat_children)) == 2
    assert struct.unpack_from('<I', container, cursor)[0] == 2
    cursor += 4
    for value, child in zip(DEFEAT_VALUES, defeat_children):
        assert struct.unpack_from('<III', container, cursor) == (voice_hash(value), 1, child), 'defeat branch must play exactly one child'
        cursor += 12
        assert objects[child][0] == 2
        assert struct.unpack_from('<I', objects[child][1], 25)[0] == voice_hash(DEFEAT_SWITCH), 'defeat sound ancestry'
    assert struct.unpack_from('<I', container, cursor)[0] == 2
    assert order.index(voice_hash(DEFEAT_SWITCH)) < order.index(voice_hash(BANK + '/chain0'))
    scene = etree.parse(str(ROOT / 'mod/Assets/AlexanderII.ast'))
    names = [e.get('text') for e in scene.iter('m_FXName')]
    assert event('DEFEAT_FROM_HUMAN') not in names, 'do not trigger both defeat recordings'
    assert not any('Play_RUSS_PA_' in name for name in names), 'Peter speech remains in scene'
    for slot in [*LINES, *extras]:
        name = event(slot)
        if slot in LINES:
            assert names.count(name) == 1, 'scene binding: ' + name
        kind, body = objects[voice_hash(name)]
        assert kind == 4 and struct.unpack_from('<I', body, 4)[0] == 1
        action_id = struct.unpack_from('<I', body, 8)[0]
        kind, action = objects[action_id]
        assert kind == 3 and action[4:6] == b'\x03\x04'
        assert struct.unpack_from('<I', action, 14)[0] == voice_hash(BANK)
        sound_id = struct.unpack_from('<I', action, 6)[0]
        if slot == 'DEFEAT':
            assert sound_id == voice_hash(DEFEAT_SWITCH), 'defeat must select through switch'
            sound_id = defeat_children[0]
        kind, sound = objects[sound_id]
        assert kind == 2 and struct.unpack_from('<I', sound, 4)[0] == 0x00010001 and sound[8] == 0
        media_id, size = struct.unpack_from('<II', sound, 9)
        assert any(mid == media_id and length == size for mid, _, length in media)
        source = sources[slot]
        source_path = ROOT / source['file']
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source['sha256'], 'source checksum: ' + slot
        with wave.open(str(source_path), 'rb') as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 3, 48000), 'source format: ' + slot
            raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
        values[values >= 0x800000] -= 0x1000000
        expected = np.clip(np.rint(values / 256.0), -32768, 32767).astype('<i2').tobytes()
        start = next(offset for mid, offset, _ in media if mid == media_id)
        wem = chunks[b'DATA'][1][start:start + size]
        wav_chunks = {}
        cursor = 12
        while cursor < len(wem):
            tag, length = struct.unpack_from('<4sI', wem, cursor)
            wav_chunks[tag] = wem[cursor + 8:cursor + 8 + length]
            cursor += 8 + length + (length % 2)
        assert struct.unpack_from('<HHI', wav_chunks[b'fmt ']) == (0xfffe, 1, 48000), 'embedded format: ' + slot
        assert wav_chunks[b'data'] == expected, 'embedded PCM differs from selected source: ' + slot
        assert order.index(sound_id) < order.index(action_id) < order.index(voice_hash(name))
    for slot in LINES:
        trigger = next(t for t in scene.findall('.//m_Triggers/Element')
                       if t.find('m_FXName').get('text') == event(slot))
        timeline = trigger.getparent().getparent()
        alias = 'AlexanderII_Voice_' + slot
        assert timeline.find('m_AnimationName').get('text') == alias
        description = etree.parse(str(ROOT / 'mod/Animations' / (alias + '.anm')))
        assert abs(float(description.findtext('m_fDuration')) - scene_duration(slot, trigger)) < 1e-5
        assert description.find('.//m_RelativePath').get('text') == alias + '.fgx'
        assert abs(float(timeline.findtext('m_fDuration')) - scene_duration(slot, trigger)) < 1e-5, 'scene duration: ' + slot
    mixer = objects[voice_hash(BANK + '/chain0')][1]
    assert mixer[16:18] == b'\x01\x00'
    assert struct.unpack_from('<f', mixer, 18)[0] == -8.0 + GAIN_DB, 'voice gain'
    _, stop = objects[voice_hash(STOP)]
    _, action = objects[struct.unpack_from('<I', stop, 8)[0]]
    assert action[4:6] == b'\x02\x01' and struct.unpack_from('<I', action, 6)[0] == voice_hash(BANK + '/chain0')
    assert struct.unpack_from('<I', mixer, 11)[0] == LEADER_SPEECH, 'native stop must reach our branch'
    assert LEADER_SPEECH not in objects, 'do not replace vanilla mixer'
    assert voice_hash(BANK + '/chain1') not in objects and voice_hash(BANK + '/chain2') not in objects
    meta = etree.parse(str(path.with_suffix('.xml')))
    assert {e.get('Name') for e in meta.findall('.//Event')} == {*(event(slot) for slot in [*LINES, *extras]), STOP}


if __name__ == '__main__':
    verify_voice()
    print('OK: voice bank, media, events, stop action and scene links (playback unverified)')


def verify_cooked_timing():
    """Check actual BLP timing: AST duration alone can silently leave the 16s idle."""
    from collections import Counter
    from verify_leader_bindings import CookedPackage
    scene = etree.parse(str(ROOT / 'mod/Assets/AlexanderII.ast'))
    expected = Counter()
    for timeline in scene.findall('.//m_Timelines/Element'):
        name = timeline.find('m_AnimationName').get('text')
        description = etree.parse(str(ROOT / 'mod/Animations' / (name + '.anm')))
        expected[round(float(description.findtext('m_fDuration')), 4)] += 1
    for platform in ('Windows', 'MacOS'):
        package = CookedPackage(ROOT / 'mod/Platforms' / platform / 'BLPs/leaders/leader_remsely_alexander_ii.blp')
        actual = Counter(round(t['Duration'], 4) for t in package.objects('TimelineSet::Timeline'))
        # Standard_Leader adds one empty timeline for its no-animation state.
        assert actual.pop(0.0, 0) == 1, 'missing DSG empty timeline'
        assert actual == expected, f'{platform}: cooked cinematic durations differ: {actual} != {expected}'
        print('voice scene durations OK:', platform)
