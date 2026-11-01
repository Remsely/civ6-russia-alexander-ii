"""Targeted review takes: friendship reply, semantic emphasis on the verb."""
import hashlib,json
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter,sosfiltfilt

def generate(model):
 root=Path.cwd()
 out=root/'art/voice/candidates/friend-accept-v2';out.mkdir(parents=True,exist_ok=True)
 ref=root/'art/voice/selected/first-meet-clean.wav'
 prompt='(A mature male Russian emperor speaks calmly and quietly, composed and dignified, natural conversational acting. Gentle sincere emphasis on the verb ценит, the following words такую дружбу are unstressed and flow softly downward. No dramatic emphasis.)'
 report=[]
 for i,seed in enumerate([311,731],1):
  text='Благодарю. Россия це́нит такую дружбу.'
  torch.manual_seed(seed)
  audio=model.generate(text=prompt+' '+text,reference_wav_path=str(ref),cfg_value=2.0,inference_timesteps=32,denoise=False,normalize=False)
  assert np.isfinite(audio).all() and len(audio)>24000
  raw=out/f'friend-accept-{i}-raw.wav';clean=out/f'friend-accept-{i}-clean.wav'
  sf.write(raw,audio,48000,subtype='PCM_24')
  filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=48000,output='sos'),audio)
  filtered=filtered/np.max(np.abs(filtered))*0.85
  sf.write(clean,filtered,48000,subtype='PCM_24')
  report.append(dict(key='ACCEPT_DECLARE_FRIEND_FROM_AI',variant=i,text='Благодарю. Россия ценит такую дружбу.',synthesis_text=text,prompt=prompt,seed=seed,steps=32,cfg=2,reference=str(ref.relative_to(root)),reference_sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),seconds=len(audio)/48000,raw=raw.name,clean=clean.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),clean_sha256=hashlib.sha256(clean.read_bytes()).hexdigest(),status='awaiting user review',reason='v1 user rejected emphasis on такую; desired emphasis on ценит'))
  (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print('DONE FRIEND REVISION',i,flush=True)

if __name__ == '__main__':
 import os
 os.environ['HF_HUB_OFFLINE']='1'
 os.environ['TRANSFORMERS_OFFLINE']='1'
 from voxcpm import VoxCPM
 model=VoxCPM(str(Path.cwd()/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
 generate(model)
