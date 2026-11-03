"""Independent Global narrator bank; diplomacy keeps its native LeaderSpeech ancestry."""
import hashlib
import json
import struct
import tempfile
import uuid
import wave
from pathlib import Path

import numpy as np
from lxml import etree
from leader_voice import ROOT, GAIN_DB

BANK = 'REMSELY_AlexanderII_Loading'
PLAY = 'Play_REMSELY_AlexanderII_LOADING_RU'
STOP = 'Stop_REMSELY_AlexanderII_Loading'
INI = 'REMSELY_AlexanderIILoadingBanks.ini'
OUT = ROOT / 'mod/Platforms/Windows/Audio'


def loading_recording():
    trial = ROOT / 'art/voice/loading-trial-manifest.json'
    if trial.exists():
        return json.loads(trial.read_text(encoding='utf-8-sig'))
    row = next(r for r in json.loads((ROOT / 'art/voice/selected/manifest.json').read_text(encoding='utf-8-sig')) if r['file'] == 'loading-ru-clean.wav')
    return dict(row, file='art/voice/selected/loading-ru-clean.wav')


def source_pcm():
    source = ROOT / loading_recording()['file']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == loading_recording()['sha256'], 'loading source checksum'
    with wave.open(str(source), 'rb') as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 3, 48000)
        raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    values = raw[:, 0] | raw[:, 1] << 8 | raw[:, 2] << 16
    values[values >= 0x800000] -= 0x1000000
    return np.clip(np.rint(values / 256.0), -32768, 32767).astype('<i2').tobytes()


def build_loading_bank(tool, objects, original_sound, chain):
    fnv = tool['fnv']
    # Clone all narrator ancestors with new IDs: its parent must not depend on
    # the InGame Speech bank. It still outputs to the existing shared speech bus.
    chain = [bytearray(body) for body in chain]
    struct.pack_into('<f', chain[0], 18, struct.unpack_from('<f', chain[0], 18)[0] + GAIN_DB)
    sound = bytearray(original_sound)
    assert sound[30:32] == b'\x01\x00'
    struct.pack_into('<f', sound, 32, loading_recording().get('sound_gain_db', 5.1))
    with tempfile.TemporaryDirectory(prefix='alexander-loading-') as temp:
        wav_path = Path(temp) / 'loading.wav'
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(source_pcm())
        wem = tool['pcm_wem'](str(wav_path))
    blob, ids = tool['build_bank'](BANK, [dict(event=PLAY, wem=wem, body=bytes(sound), plugin=0x00010001)], chain=[bytes(b) for b in chain])
    stop_event = objects[fnv('Stop_Leader_Speech')][1]
    stop_action = bytearray(objects[struct.unpack_from('<I', stop_event, 8)[0]][1])
    stop_id = fnv(BANK + '/stop')
    struct.pack_into('<I', stop_action, 0, stop_id)
    struct.pack_into('<I', stop_action, 6, fnv(BANK + '/chain0'))
    built = tool['read_hirc'](blob) + [(3, bytes(stop_action)), (4, struct.pack('<III', fnv(STOP), 1, stop_id))]
    assert not set(objects) & {struct.unpack_from('<I', b)[0] for _, b in built}, 'vanilla object collision'
    (OUT / (BANK + '.bnk')).write_bytes(tool['assemble'](BANK, built, [(fnv(BANK + '/media0'), wem)]))
    (OUT / INI).write_text('[Global]\n!' + BANK + '.bnk\n\n[Menu]\n\n[InGame]\n\n[2D]\n\n[3D]\n\n[FMV]\n', encoding='utf-8')
    meta = etree.Element('SoundBanksInfo', Platform='Windows', BasePlatform='Windows', SchemaVersion='10', SoundbankVersion='113')
    bank = etree.SubElement(etree.SubElement(meta, 'SoundBanks'), 'SoundBank', Id=str(ids['bank']), Language='SFX')
    etree.SubElement(bank, 'ShortName').text = BANK
    etree.SubElement(bank, 'Path').text = BANK + '.bnk'
    events = etree.SubElement(bank, 'IncludedEvents')
    for name in (PLAY, STOP):
        etree.SubElement(events, 'Event', Id=str(fnv(name)), Name=name, GUID='{' + str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper() + '}')
    memory = etree.SubElement(bank, 'IncludedMemoryFiles')
    file = etree.SubElement(memory, 'File', Id=str(fnv(BANK + '/media0')), Language='SFX')
    etree.SubElement(file, 'ShortName').text = Path(loading_recording()['file']).name
    etree.SubElement(file, 'Path').text = str(fnv(BANK + '/media0')) + '.wem'
    etree.ElementTree(meta).write(str(OUT / (BANK + '.xml')), encoding='utf-8', xml_declaration=True, pretty_print=True)


def verify_loading_voice():
    from verify_voice import voice_hash as fnv
    data = (OUT / (BANK + '.bnk')).read_bytes()
    chunks = {}; position = 0
    while position < len(data):
        tag, size = struct.unpack_from('<4sI', data, position)
        assert position + 8 + size <= len(data), 'truncated loading bank'
        chunks[tag] = data[position + 8:position + 8 + size]; position += 8 + size
    assert struct.unpack_from('<II', chunks[b'BKHD']) == (113, fnv(BANK))
    hirc = chunks[b'HIRC']; count = struct.unpack_from('<I', hirc)[0]; position = 4; objects = {}
    for _ in range(count):
        kind, size = struct.unpack_from('<BI', hirc, position); body = hirc[position + 5:position + 5 + size]
        oid = struct.unpack_from('<I', body)[0]; assert oid not in objects
        objects[oid] = (kind, body); position += 5 + size
    assert position == len(hirc)
    event = objects[fnv(PLAY)][1]; action = objects[struct.unpack_from('<I', event, 8)[0]][1]
    assert action[4:6] == b'\x03\x04' and struct.unpack_from('<I', action, 14)[0] == fnv(BANK)
    kind, sound = objects[struct.unpack_from('<I', action, 6)[0]]
    assert kind == 2 and struct.unpack_from('<I', sound, 4)[0] == 0x00010001 and sound[8] == 0
    assert struct.unpack_from('<I', sound, 25)[0] == fnv(BANK + '/chain0')
    assert abs(struct.unpack_from('<f', sound, 32)[0] - loading_recording().get('sound_gain_db', 5.1)) < 1e-5
    media_id, size = struct.unpack_from('<II', sound, 9)
    mid, offset, length = struct.unpack('<III', chunks[b'DIDX'])
    assert mid == media_id and length == size
    wem = chunks[b'DATA'][offset:offset + length]; position = 12; wav_chunks = {}
    while position < len(wem):
        tag, length = struct.unpack_from('<4sI', wem, position)
        wav_chunks[tag] = wem[position + 8:position + 8 + length]; position += 8 + length + length % 2
    assert wav_chunks[b'data'] == source_pcm(), 'loading embedded PCM differs from selected source'
    assert struct.unpack_from('<HHI', wav_chunks[b'fmt ']) == (0xfffe, 1, 48000)
    chain_gain = 0.0
    for index in range(3):
        kind, mixer = objects[fnv(BANK + '/chain' + str(index))]; assert kind == 7
        prop_count = mixer[16]
        properties = {mixer[17 + i]: struct.unpack_from('<f', mixer, 17 + prop_count + 4 * i)[0] for i in range(prop_count)}
        chain_gain += properties.get(0, 0.0)
        parent = struct.unpack_from('<I', mixer, 11)[0]
        assert parent == (fnv(BANK + '/chain' + str(index + 1)) if index < 2 else 0), 'loading depends on InGame parent'
    assert struct.unpack_from('<I', mixer, 7)[0] == fnv('Speech Bus'), 'loading speech bus'
    assert abs(chain_gain + 6.0) < 1e-5, 'loading mixer gain changed'
    row = loading_recording()
    assert not row.get('status', '').startswith('rejected'), 'rejected loading take must not be installed'
    if (ROOT / 'art/voice/loading-trial-manifest.json').exists():
        assert 'transcript_check' in row, 'new loading take needs a spoken-ending check'
    if 'transcript_check' in row:
        transcript = json.loads((ROOT / row['transcript_check']).read_text(encoding='utf-8'))
        assert transcript['ending_matches'], 'loading speech ending is incomplete'
        assert transcript['content_matches'], 'loading speech contains missing or foreign text'
        assert transcript['audio_sha256'] == row['sha256'], 'stale loading transcript check'
        assert transcript['expected_text'] == row['text'], 'loading transcript checked against different text'
    if 'source_lufs' in row:
        assert abs(row['source_lufs'] + chain_gain + row['sound_gain_db'] - row['estimated_prebus_lufs']) < 0.01, 'loading loudness estimate'
        assert row['true_peak_db'] + chain_gain + row['sound_gain_db'] <= -0.49, 'loading gain leaves no peak headroom'
    stop = objects[fnv(STOP)][1]; action = objects[struct.unpack_from('<I', stop, 8)[0]][1]
    assert action[4:6] == b'\x02\x01' and struct.unpack_from('<I', action, 6)[0] == fnv(BANK + '/chain0')
    assert (OUT / INI).read_text().split('[Menu]')[0].strip() == '[Global]\n!' + BANK + '.bnk', 'loading must be Global'
    meta = etree.parse(str(OUT / (BANK + '.xml')))
    assert {e.get('Name') for e in meta.findall('.//Event')} == {PLAY, STOP}
    texts = etree.parse(str(ROOT / 'mod/Text/ru_RU.xml'))
    assert texts.findtext(".//Replace[@Tag='LOC_LOADING_INFO_LEADER_REMSELY_ALEXANDER_II']/Text") == loading_recording()['text'], 'loading voice/subtitle mismatch'
    modinfo = etree.parse(str(ROOT / 'mod/RemselysAlexanderII.modinfo'))
    early = modinfo.find("./FrontEndActions/UpdateAudio[@id='REMSELY_FrontEnd_Audio']")
    assert early is not None and any(f.text.endswith(BANK + '.bnk') for f in early.findall('File')), 'missing FrontEnd bank'
    hook = modinfo.find("./FrontEndActions/ImportFiles[@id='REMSELY_LoadScreen_Voice']")
    assert hook is not None, 'loading must run before InGame addins'
    files = [f.text for f in hook.findall('File')]
    listed = [f.text for f in modinfo.findall('./Files/File')]
    assert all(f in files and f in listed for f in ('UI/LoadScreen.lua', 'UI/RemselysAlexanderII_LoadScreen.lua', 'UI/RemselysAlexanderII_LoadingEraDurations.lua')), 'missing FrontEnd loading hook file'
    wrapper = (ROOT / 'mod/UI/LoadScreen.lua').read_text(encoding='utf-8')
    assert wrapper.rstrip().endswith('include("RemselysAlexanderII_LoadScreen");'), 'loading extension must run after vanilla initialization'
