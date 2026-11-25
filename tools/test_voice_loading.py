"""Catch the original loading-speech failures in the built bank and registration."""
import struct
from pathlib import Path

import pytest
from loading_voice import BANK, INI, OUT, verify_loading_voice
from verify_voice import voice_hash


def test_loading_bank_and_early_registration():
    verify_loading_voice()


def test_ingame_only_loading_bank_is_rejected(monkeypatch):
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda self, *a, **kw: '[Global]\n\n[Menu]\n\n[InGame]\n!' + BANK + '.bnk\n' if self == OUT / INI else original(self, *a, **kw))
    with pytest.raises(AssertionError, match='must be Global'):
        verify_loading_voice()


def test_ingame_parent_dependency_is_rejected(monkeypatch):
    bank = OUT / (BANK + '.bnk')
    original = Path.read_bytes
    damaged = bytearray(original(bank)); pos = 0
    while pos < len(damaged):
        tag, size = struct.unpack_from('<4sI', damaged, pos)
        if tag == b'HIRC':
            cursor = pos + 12
            for _ in range(struct.unpack_from('<I', damaged, pos + 8)[0]):
                kind, length, oid = struct.unpack_from('<BII', damaged, cursor)
                if oid == voice_hash(BANK + '/chain0'):
                    struct.pack_into('<I', damaged, cursor + 5 + 11, 854467727)
                    break
                cursor += 5 + length
            break
        pos += 8 + size
    monkeypatch.setattr(Path, 'read_bytes', lambda self: bytes(damaged) if self == bank else original(self))
    with pytest.raises(AssertionError, match='InGame parent'):
        verify_loading_voice()


def test_incomplete_spoken_ending_is_rejected(monkeypatch):
    import json
    import loading_voice
    original = Path.read_text
    row = loading_voice.loading_recording()
    report_path = loading_voice.ROOT / row['transcript_check']
    report = json.loads(original(report_path, encoding='utf-8'))
    report['ending_matches'] = False
    monkeypatch.setattr(Path, 'read_text', lambda self, *a, **kw: json.dumps(report) if self == report_path else original(self, *a, **kw))
    with pytest.raises(AssertionError, match='ending is incomplete'):
        verify_loading_voice()


def test_english_event_cannot_play_russian_media(monkeypatch):
    import loading_voice
    if 'en' not in loading_voice.loading_recordings():
        pytest.skip('English narration not integrated yet')
    bank = OUT / (BANK + '.bnk')
    original = Path.read_bytes
    damaged = bytearray(original(bank))
    pos = 0
    bodies = {}
    while pos < len(damaged):
        tag, size = struct.unpack_from('<4sI', damaged, pos)
        if tag == b'HIRC':
            cursor = pos + 12
            for _ in range(struct.unpack_from('<I', damaged, pos + 8)[0]):
                kind, length, oid = struct.unpack_from('<BII', damaged, cursor)
                bodies[oid] = cursor + 5
                cursor += 5 + length
            break
        pos += 8 + size
    ru = bodies[voice_hash(BANK + '/sound0')]
    en = bodies[voice_hash(BANK + '/sound1')]
    damaged[en + 9:en + 17] = damaged[ru + 9:ru + 17]
    monkeypatch.setattr(Path, 'read_bytes', lambda self: bytes(damaged) if self == bank else original(self))
    with pytest.raises(AssertionError, match='embedded PCM differs'):
        verify_loading_voice()
