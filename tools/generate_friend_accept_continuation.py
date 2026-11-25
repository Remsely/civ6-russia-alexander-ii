"""Review variants using approved praise audio as a prosody continuation prompt."""
import hashlib,json
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter,sosfiltfilt

def generate(model):
 root=Path.cwd();out=root/'art/voice/candidates/friend-accept-v3';out.mkdir(parents=True,exist_ok=True)
 ref=root/'art/voice/selected/first-meet-clean.wav'
 prosody=root/'art/voice/selected/kudos-clean.wav'
 transcript='Ваше государство хорошо управляется. Такой порядок служит народу.'
 report=[]
 for i,text in enumerate(['Благодарю. Россия ценит такую дружбу.','Благодарю. Россия ценит дружбу.'],1):
  raw=out/f'friend-accept-{i}-raw.wav';clean=out/f'friend-accept-{i}-clean.wav'
  if raw.exists() or clean.exists():raise FileExistsError(raw)
  torch.manual_seed(731)
  audio=model.generate(text=text,prompt_wav_path=str(prosody),prompt_text=transcript,reference_wav_path=str(ref),cfg_value=2.0,inference_timesteps=32,denoise=False,normalize=False)
  assert np.isfinite(audio).all() and len(audio)>24000
  sf.write(raw,audio,48000,subtype='PCM_24')
  filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=48000,output='sos'),audio)
  filtered=filtered/np.max(np.abs(filtered))*0.85
  sf.write(clean,filtered,48000,subtype='PCM_24')
  report.append(dict(key='ACCEPT_DECLARE_FRIEND_FROM_AI',variant=i,text=text,prompt_text=transcript,prompt_wav_path=str(prosody.relative_to(root)),prompt_sha256=hashlib.sha256(prosody.read_bytes()).hexdigest(),seed=731,steps=32,cfg=2,reference=str(ref.relative_to(root)),reference_sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),seconds=len(audio)/48000,raw=raw.name,clean=clean.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),clean_sha256=hashlib.sha256(clean.read_bytes()).hexdigest(),status='awaiting user review; variant 2 proposes a text change',reason='v1 and v2 emphasis on такую and uneven delivery rejected; use audio continuation without style instructions'))
  (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print('DONE FRIEND V3',i,flush=True)

if __name__ == '__main__':
 import os
 os.environ['HF_HUB_OFFLINE']='1'
 os.environ['TRANSFORMERS_OFFLINE']='1'
 from voxcpm import VoxCPM
 model=VoxCPM(str(Path.cwd()/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
 generate(model)
