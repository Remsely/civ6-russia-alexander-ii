"""Review a user-proposed friendship reply at 32 and 64 steps."""
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
root=Path.cwd();out=root/'art/voice/candidates/friend-appreciation-v1';out.mkdir(parents=True,exist_ok=True)
ref=root/'art/voice/selected/first-meet-clean.wav'
prompt='(A mature male Russian emperor speaks in Russian, measured pace, calm composed and dignified, quiet even tone, restrained natural conversational acting, clear pronunciation.)'
model=VoxCPM(str(root/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
report=[]
for steps in [32,64]:
 key='ACCEPT_DECLARE_FRIEND_FROM_AI'
 text='Россия очень ценит дружбу с вами. Благодарю.'
 seed=731
 stem='friend-appreciation-'+str(steps)
 raw=out/f'{stem}-raw.wav';clean=out/f'{stem}-clean.wav'
 if raw.exists() or clean.exists():raise FileExistsError(raw)
 torch.manual_seed(seed)
 audio=model.generate(text=prompt+' '+text,reference_wav_path=str(ref),cfg_value=2.0,inference_timesteps=steps,denoise=False,normalize=False)
 assert len(audio)>24000 and np.isfinite(audio).all()
 sf.write(raw,audio,48000,subtype='PCM_24')
 filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=48000,output='sos'),audio)
 filtered=filtered/np.max(np.abs(filtered))*0.85
 sf.write(clean,filtered,48000,subtype='PCM_24')
 report.append(dict(key=key,text=text,prompt=prompt,reference=str(ref.relative_to(root)),reference_sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),seed=seed,steps=steps,cfg=2,sample_rate=48000,seconds=len(audio)/48000,raw=raw.name,clean=clean.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),clean_sha256=hashlib.sha256(clean.read_bytes()).hexdigest(),status='awaiting user review',processing='Butterworth order 2 70-9500Hz sosfiltfilt peak 0.85 PCM24',english_text='Russia greatly values your friendship. Thank you.',comparison_note='Same text, seed and reference; only inference steps differ. Trial wording, not yet selected.'))
 (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('DONE',key,steps,len(audio)/48000,flush=True)
print('COMPLETE',flush=True)
