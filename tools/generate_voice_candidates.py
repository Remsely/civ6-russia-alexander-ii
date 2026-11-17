"""Generate review-only diplomatic voice candidates; never replace selected takes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SELECTED = {
    'FIRST_MEET': 'first-meet-clean.wav',
    'DECLARE_WAR_FROM_AI': 'declare-war-ai-clean.wav',
    'DECLARE_WAR_FROM_HUMAN': 'declare-war-human-clean.wav',
    'KUDO_EXIT': 'kudos-clean.wav',
    'WARNING_EXIT': 'warning-clean.wav',
    'DEFEAT_FROM_AI': 'defeat-ai-clean.wav',
}
PROMPT = '(A mature male Russian emperor speaks in Russian, measured pace, calm composed and dignified, quiet even tone, restrained natural conversational acting, clear pronunciation.)'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='art/voice/candidates/diplomacy-v1')
    parser.add_argument('--seed', type=int, default=731)
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to(ROOT / 'art/voice/candidates'):
        raise ValueError('Output must be inside art/voice/candidates')
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in ET.parse(ROOT / 'mod/Text/ru_RU.xml').getroot().iter('Replace'):
        tag = row.get('Tag', '')
        suffix = '_LEADER_REMSELY_ALEXANDER_II_ANY'
        if tag.startswith('LOC_DIPLO_') and tag.endswith(suffix):
            key = tag[len('LOC_DIPLO_'):-len(suffix)]
            if key.endswith('_REASON'):
                continue
            text = row.findtext('Text')
            rows.append(dict(key=key, tag=tag, text=text))
    assert len(rows) == 31, len(rows)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import soundfile as sf
    import torch
    from scipy.signal import butter, sosfiltfilt
    from voxcpm import VoxCPM
    ref = ROOT / 'art/voice/selected/first-meet-clean.wav'
    model = VoxCPM(str(ROOT / 'art/build/voice/voxcpm2-model'), enable_denoiser=False, optimize=False, device='cuda')
    report_path = out / 'manifest.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else []
    for row in rows:
        key = row['key']
        if key in SELECTED:
            continue
        if any(item['key'] == key for item in report):
            print('EXISTS', key, flush=True)
            continue
        spoken = row['text'].replace(' (Осуждает вас)', '')
        prompt = PROMPT
        if key == 'DEFEAT_FROM_HUMAN':
            prompt = '(A mature male Russian emperor speaks quietly in Russian, slow measured pace, composed and dignified, restrained grief and weary acceptance, subdued falling intonation, natural conversational acting, clear pronunciation.)'
        torch.manual_seed(args.seed)
        audio = model.generate(text=prompt + ' ' + spoken, reference_wav_path=str(ref), cfg_value=2.0, inference_timesteps=32, denoise=False, normalize=False)
        sr = 48000
        assert len(audio) > sr / 2 and np.isfinite(audio).all()
        stem = key.lower().replace('_', '-')
        raw = out / (stem + '-raw.wav')
        clean = out / (stem + '-clean.wav')
        if raw.exists() or clean.exists():
            raise FileExistsError(stem)
        sf.write(raw, audio, sr, subtype='PCM_24')
        filtered = sosfiltfilt(butter(2, [70, 9500], btype='bandpass', fs=sr, output='sos'), audio)
        filtered = filtered / np.max(np.abs(filtered)) * 0.85
        sf.write(clean, filtered, sr, subtype='PCM_24')
        report.append(dict(**row, spoken_text=spoken, prompt=prompt, reference=str(ref.relative_to(ROOT)), reference_sha256=digest(ref), seed=args.seed, steps=32, cfg=2.0, sample_rate=sr, seconds=len(audio)/sr, raw=raw.name, raw_sha256=digest(raw), clean=clean.name, clean_sha256=digest(clean), status='awaiting user review', processing='Butterworth order 2 bandpass 70-9500Hz, sosfiltfilt, peak 0.85, PCM24'))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('DONE', key, len(audio)/sr, flush=True)
    page = ['# Реплики Александра II для прослушивания', '', 'Шесть выбранных записей и 25 новых пробных дублей. Новые дубли еще не одобрены и не установлены в игру.', '']
    for i, row in enumerate(rows, 1):
        key = row['key']
        if key in SELECTED:
            path = ROOT / 'art/voice/selected' / SELECTED[key]
            status = 'выбранная запись'
        else:
            item = next(item for item in report if item['key'] == key)
            path = out / item['clean']
            status = 'новая проба, ожидает оценки'
        page += [f"## {i}. {key} — {status}", '', row['text'], '', f'![Прослушать]({path.as_posix()})', '']
    page += ['## Загрузка — пока без записи', '']
    for language in ['ru_RU', 'en_US']:
        tree = ET.parse(ROOT / f'mod/Text/{language}.xml')
        text = next(row.findtext('Text') for row in tree.getroot().iter('Replace') if row.get('Tag') == 'LOC_LOADING_INFO_LEADER_REMSELY_ALEXANDER_II')
        page += [f'### {language}', '', text, '']
    (out / 'review.md').write_text('\n'.join(page), encoding='utf-8')
    print('COMPLETE', len(report), flush=True)

if __name__ == '__main__':
    main()
