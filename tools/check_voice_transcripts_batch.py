"""Check candidate transcripts with a single CPU Whisper model.

Accepts one or more manifests produced by generate_voice_review_round.py.
The report is incremental: a row is reused only if its audio hash and expected
text match. ASR results are aids to listening, never proof of performance or
even of an uninterrupted ending.
"""

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from check_voice_transcript import compare_transcript


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, action='append', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--follow', action='store_true', help='Watch partial manifests until --expected rows or idle timeout')
    parser.add_argument('--expected', type=int, help='Total rows in all manifests before follow finishes')
    parser.add_argument('--poll-seconds', type=float, default=10)
    parser.add_argument('--idle-timeout', type=float, default=600)
    args = parser.parse_args()
    if args.threads < 1 or args.poll_seconds <= 0 or args.idle_timeout <= 0:
        parser.error('threads, poll-seconds and idle-timeout must be positive')
    if args.follow and (args.expected is None or args.expected < 1):
        parser.error('--follow requires a positive --expected')

    root = Path(__file__).resolve().parents[1]
    report = args.report.resolve()
    manifests = [path.resolve() for path in args.manifest]
    if report in manifests:
        parser.error('report cannot overwrite an input manifest')
    if report.exists():
        payload = json.loads(report.read_text(encoding='utf-8-sig'))
        if payload.get('schema') != 1:
            raise ValueError('Unexpected report schema; refusing to overwrite')
        rows = payload['items']
    else:
        rows = []
    indexed = {(row['manifest'], row['key']): row for row in rows}
    model = None
    last_progress = time.monotonic()

    while True:
        available = []
        for manifest in manifests:
            try:
                items = json.loads(manifest.read_text(encoding='utf-8-sig'))
            except (FileNotFoundError, json.JSONDecodeError) as error:
                if not args.follow:
                    raise
                print(f'WAIT {manifest}: {error}', flush=True)
                continue
            if not isinstance(items, list):
                raise ValueError(f'Expected manifest list: {manifest}')
            for item in items:
                audio = (manifest.parent / item['clean']).resolve()
                available.append((manifest, item, audio))

        processed = 0
        for manifest, item, audio in available:
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            identity = (str(manifest), item['key'])
            previous = indexed.get(identity)
            if (previous and previous['audio_sha256'] == digest
                    and previous['expected_text'] == item['text']):
                continue
            if model is None:
                import numpy as np
                import soundfile as sf
                from scipy.signal import resample_poly
                from faster_whisper import WhisperModel
                model = WhisperModel(str(root / 'art/build/voice/whisper-small'), device='cpu',
                                     compute_type='int8', cpu_threads=args.threads, local_files_only=True)
            samples, sample_rate = sf.read(audio)
            if samples.ndim != 1 or sample_rate != 48000 or not np.isfinite(samples).all():
                raise ValueError(f'Invalid mono 48 kHz PCM audio: {audio}')
            chunks, _ = model.transcribe(resample_poly(samples, 1, 3).astype(np.float32),
                                         language='ru', beam_size=5, vad_filter=False)
            segments = [dict(start=s.start, end=s.end, text=s.text.strip()) for s in chunks]
            actual = ' '.join(segment['text'] for segment in segments)
            row = dict(manifest=str(manifest), key=item['key'], number=item['number'], audio=str(audio),
                       audio_sha256=digest, seconds=len(samples) / sample_rate, expected_text=item['text'],
                       recognized_text=actual, **compare_transcript(item['text'], actual), segments=segments)
            indexed[identity] = row
            atomic_write(report, dict(schema=1, model='whisper-small', device='cpu', compute_type='int8',
                                      limitation='ASR can be wrong; listening is required for speech, stress, acting and endings.',
                                      items=sorted(indexed.values(), key=lambda x: (x['number'], x['manifest'], x['key']))))
            processed += 1
            last_progress = time.monotonic()
            print(f"DONE {row['number']} {row['key']} match={row['content_matches']} "
                  f"similarity={row['word_similarity']:.3f} {actual}", flush=True)

        print(f'CHECKED available={len(available)} cached={len(indexed)} new={processed}', flush=True)
        if not args.follow or len(available) >= args.expected and len(indexed) >= args.expected:
            return
        if time.monotonic() - last_progress >= args.idle_timeout:
            print('STOP idle timeout reached; incomplete manifests can be resumed', flush=True)
            return
        time.sleep(args.poll_seconds)


if __name__ == '__main__':
    main()
