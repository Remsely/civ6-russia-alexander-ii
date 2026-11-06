"""Check a candidate's spoken ending locally; run with the VoxCPM environment.

ASR catches missing words, but cannot approve acting, stress, timbre or articulation.
The expected text comes from a saved review plan or trial manifest, not a prompt.
"""
import argparse
import hashlib
import difflib
import json
import re
from pathlib import Path


def words(text):
    return re.findall(r'[а-яa-z]+', text.lower().replace('ё', 'е'))


def compare_transcript(expected, actual, language="ru"):
    expected_words, actual_words = words(expected), words(actual)
    head = expected_words[:5]
    beginning = actual_words[:len(head)] == head
    tail = expected_words[-5:]
    ending = actual_words[-len(tail):] == tail
    similarity = difflib.SequenceMatcher(None, expected_words, actual_words).ratio()
    foreign = re.findall(r'[A-Za-z]+' if language == 'ru' else r'[А-Яа-яЁё]+', actual)
    return dict(beginning_matches=beginning, expected_first_words=head, recognized_first_words=actual_words[:len(head)], expected_last_words=tail, recognized_last_words=actual_words[-len(tail):],
                ending_matches=ending, word_similarity=similarity, unexpected_latin_words=foreign if language == "ru" else [], unexpected_foreign_words=foreign,
                content_matches=beginning and ending and similarity >= 0.9 and not foreign)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--word-timings', action='store_true')
    parser.add_argument('--language', choices=('ru', 'en'), default='ru')
    args = parser.parse_args()
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from faster_whisper import WhisperModel
    root = Path(__file__).resolve().parents[1]
    meta = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if 'items' in meta:
        assert len(meta['items']) == 1
        meta = meta['items'][0]
    if isinstance(meta, list):
        assert len(meta) == 1
        meta = meta[0]
    audio, sr = sf.read(args.audio)
    assert audio.ndim == 1 and sr == 48000
    model = WhisperModel(str(root / 'art/build/voice/whisper-small'), device='cpu', compute_type='int8', local_files_only=True)
    segments, _ = model.transcribe(resample_poly(audio, 1, 3).astype(np.float32), language=args.language, beam_size=5, vad_filter=False, word_timestamps=args.word_timings)
    rows = [dict(start=s.start, end=s.end, text=s.text.strip(), words=[dict(start=float(w.start), end=float(w.end), word=w.word.strip(), probability=float(w.probability)) for w in (s.words or [])]) for s in segments]
    actual = ' '.join(s['text'] for s in rows)
    comparison = compare_transcript(meta['text'], actual, args.language)
    result = dict(audio=str(args.audio), audio_sha256=hashlib.sha256(args.audio.read_bytes()).hexdigest(), seconds=len(audio) / sr, expected_text=meta['text'], recognized_text=actual,
                  **comparison, language=args.language, segments=rows,
                  limitation='ASR only; listening review still required; matching last words does not prove all words or phonemes are correct')
    if args.word_timings:
        aligned = [w for r in rows for w in r['words'] if w['end'] > w['start']]
        durations = [w['end'] - w['start'] for w in aligned]
        gaps = [max(0.0, b['start'] - a['end']) for a, b in zip(aligned, aligned[1:])]
        result['timing'] = dict(aligned_words=len(aligned), median_word_seconds=float(np.median(durations)),
                                total_word_seconds=float(sum(durations)), total_gaps_seconds=float(sum(gaps)))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(actual, flush=True)
    print('Ending matches:', result['ending_matches'], 'whole content matches:', result['content_matches'], 'word similarity:', round(result['word_similarity'], 3), flush=True)
    return 0 if result['content_matches'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
