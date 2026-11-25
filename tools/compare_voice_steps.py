"""Controlled 32/64 step comparison; fixed seed/text/audio within each pair."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import hashlib,json,time
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter,sosfiltfilt
from voxcpm import VoxCPM
root=Path.cwd();out=root/'art/voice/candidates/prosody-steps-v1';out.mkdir(parents=True,exist_ok=True)
tree=ET.parse(root/'reference/vanilla/Base/Text/Vanilla_ru_RU.xml')
transcript=next(row.findtext('Text') for row in tree.getroot().iter('Replace') if row.get('Tag')=='LOC_LOADING_INFO_LEADER_PETER_GREAT')
cases=[dict(key='loading',text='Добро пожаловать в Зимний дворец, император Александр. От берегов Балтики до Тихого океана раскинулась ваша держава.',prompt=root/'art/build/voice/integration/narrator/ru-peter-loading.wav',transcript=transcript),dict(key='friend',text='Благодарю. Россия ЦЕНИТ такую дружбу.',prompt=root/'art/voice/selected/declare-war-human-clean.wav',transcript='Я долго искал мира. Теперь его нет, и вина лежит на вас.')]
model=VoxCPM(str(root/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
report=[]
for case in cases:
 for steps in [32,64]:
  stem=f"{case['key']}-{steps}"
  raw=out/f'{stem}-raw.wav';clean=out/f'{stem}-clean.wav'
  if raw.exists() or clean.exists():raise FileExistsError(raw)
  torch.manual_seed(731)
  started=time.perf_counter()
  audio=model.generate(text=case['text'],prompt_wav_path=str(case['prompt']),prompt_text=case['transcript'],reference_wav_path=str(case['prompt']),cfg_value=2.0,inference_timesteps=steps,denoise=False,normalize=False)
  elapsed=time.perf_counter()-started
  assert np.isfinite(audio).all() and len(audio)>24000
  sf.write(raw,audio,48000,subtype='PCM_24')
  filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=48000,output='sos'),audio)
  filtered=filtered/np.max(np.abs(filtered))*0.85
  sf.write(clean,filtered,48000,subtype='PCM_24')
  report.append(dict(key=case['key'],synthesis_text=case['text'],prompt_wav=str(case['prompt'].relative_to(root)),prompt_text=case['transcript'],prompt_sha256=hashlib.sha256(case['prompt'].read_bytes()).hexdigest(),seed=731,steps=steps,cfg=2,sample_rate=48000,seconds=len(audio)/48000,inference_seconds=elapsed,raw=raw.name,clean=clean.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),clean_sha256=hashlib.sha256(clean.read_bytes()).hexdigest(),status='awaiting user review',processing='Butterworth order 2 70-9500Hz sosfiltfilt peak 0.85 PCM24'))
  (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print('DONE',stem,len(audio)/48000,elapsed,flush=True)
print('COMPLETE COMPARISON',flush=True)
