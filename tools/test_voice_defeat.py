"""Regression checks against the built defeat switch, not source-code spelling."""
import struct
from pathlib import Path
import pytest
from verify_voice import verify_voice, voice_hash
from leader_voice import ROOT, BANK, DEFEAT_SWITCH, DEFEAT_GROUP


def test_bank_and_both_defeat_recordings():
    verify_voice()


def switch_offset(data):
    pos = 0
    while pos < len(data):
        tag, size = struct.unpack_from('<4sI', data, pos)
        if tag == b'HIRC':
            cursor = pos + 12
            count = struct.unpack_from('<I', data, pos + 8)[0]
            for _ in range(count):
                kind, length, oid = struct.unpack_from('<BII', data, cursor)
                if oid == voice_hash(DEFEAT_SWITCH):
                    assert kind == 6
                    return cursor + 5, length
                cursor += 5 + length
        pos += 8 + size
    raise AssertionError('missing switch')


@pytest.mark.parametrize('fault', ['same_recording', 'continuous_switch'])
def test_invalid_defeat_switch_is_rejected(monkeypatch, fault):
    bank = ROOT / 'mod/Platforms/Windows/Audio' / (BANK + '.bnk')
    original = Path.read_bytes
    damaged = bytearray(original(bank))
    offset, size = switch_offset(damaged)
    group = damaged.index(struct.pack('<I', voice_hash(DEFEAT_GROUP)), offset, offset + size)
    if fault == 'continuous_switch':
        damaged[group + 8] = 1
        message = 'must not change during playback'
    else:
        # group, default, validation, child count, two children, mapping count,
        # first (value, count, child), second (value, count, child).
        first_child = struct.unpack_from('<I', damaged, group + 33)[0]
        struct.pack_into('<I', damaged, group + 45, first_child)
        message = 'exactly one child'
    monkeypatch.setattr(Path, 'read_bytes', lambda self: bytes(damaged) if self == bank else original(self))
    with pytest.raises(AssertionError, match=message):
        verify_voice()
