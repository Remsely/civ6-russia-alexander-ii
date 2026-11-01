"""Review-only longer loading narration using local vanilla narrator references."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import hashlib,json
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter,sosfiltfilt
from voxcpm import VoxCPM
root=Path.cwd()
out=root/'art/voice/candidates/loading-v1';out.mkdir(parents=True,exist_ok=True)
draft=(root/'docs/voice-loading-draft.ru.md').read_text(encoding='utf-8-sig')
texts={'ru':draft.split('## Русский\n\n')[1].split('\n\n## English')[0].strip(),'en':draft.split('## English\n\n')[1].strip()}
model=VoxCPM(str(root/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
report_path=out/'manifest.json'
report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else []
for lang,text in texts.items():
 if any(item['language']==lang for item in report):
  print('EXISTS LOADING',lang,flush=True)
  continue
 ref=root/f'art/build/voice/integration/narrator/{lang}-narrator-reference.wav'
 prompt='(A mature male narrator speaks '+('Russian' if lang=='ru' else 'English')+' with calm authority, rich resonant voice, dignified measured storytelling, thoughtful and inspiring, clear natural speech.)'
 # Sentence blocks avoid long-form truncation; keep every generated part for review.
 import re
 blocks=re.split(r'(?<=[.!?])\s+',text)
 parts=[]
 for i,block in enumerate(blocks,1):
  part_path=out/f'{lang}-{i:02}-raw.wav'
  if part_path.exists():
   audio,sr=sf.read(part_path)
   assert sr==48000
   parts.append(audio)
   if i<len(blocks):parts.append(np.zeros(12000,dtype=np.float32))
   continue
  torch.manual_seed(731)
  audio=model.generate(text=prompt+' '+block,reference_wav_path=str(ref),cfg_value=2.0,inference_timesteps=32,denoise=False,normalize=False)
  assert np.isfinite(audio).all() and len(audio)>24000
  sf.write(out/f'{lang}-{i:02}-raw.wav',audio,48000,subtype='PCM_24')
  parts.append(audio)
  if i<len(blocks):parts.append(np.zeros(12000,dtype=np.float32))
  print('DONE',lang,i,len(audio)/48000,flush=True)
 audio=np.concatenate(parts)
 raw=out/f'loading-{lang}-raw.wav';clean=out/f'loading-{lang}-clean.wav'
 sf.write(raw,audio,48000,subtype='PCM_24')
 filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=48000,output='sos'),audio)
 filtered=filtered/np.max(np.abs(filtered))*0.85
 sf.write(clean,filtered,48000,subtype='PCM_24')
 report.append(dict(language=lang,text=text,prompt=prompt,seed=731,steps=32,cfg=2,reference=str(ref.relative_to(root)),reference_sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),source='Base/Platforms/Windows/audio/'+('Russian' if lang=='ru' else 'English(US)')+'/Speech_Localized.xml DOM_LEAD_PET.wav',seconds=len(audio)/48000,raw=raw.name,clean=clean.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),clean_sha256=hashlib.sha256(clean.read_bytes()).hexdigest(),status='draft text and voice awaiting user review',join_silence_seconds=0.25))
 (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('COMPLETE LOADING',flush=True)
