"""Render a saved review plan without replacing selected or installed recordings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('plan')
 args=parser.parse_args()
 root=Path(__file__).resolve().parents[1]
 plan_path=(root/args.plan).resolve()
 plan=json.loads(plan_path.read_text(encoding='utf-8-sig'))
 out=(root/plan['output']).resolve()
 if not out.is_relative_to(root/'art/voice/candidates'):raise ValueError('Candidate output only')
 out.mkdir(parents=True,exist_ok=True)
 os.environ['HF_HUB_OFFLINE']='1'
 os.environ['TRANSFORMERS_OFFLINE']='1'
 import numpy as np
 import soundfile as sf
 import torch
 from scipy.signal import butter,sosfiltfilt
 from voxcpm import VoxCPM
 report_path=out/'manifest.json'
 report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else []
 model=VoxCPM(str(root/'art/build/voice/voxcpm2-model'),enable_denoiser=False,optimize=False,device='cuda')
 sr=plan['sample_rate']
 for item in plan['items']:
  existing=next((row for row in report if row['key']==item['key']),None)
  if existing:
   assert existing['text']==item['text'] and existing['synthesis_text']==item['synthesis_text']
   for kind in ['raw','clean']:assert sha(out/existing[kind])==existing[kind+'_sha256']
   print('EXISTS',item['number'],item['key'],flush=True)
   continue
  reference=root/item['reference'];prompt=root/item['prompt_wav']
  stem=item['key'].lower().replace('_','-')
  raw=out/f'{stem}-raw.wav';clean=out/f'{stem}-clean.wav'
  if raw.exists() or clean.exists():raise FileExistsError(raw)
  texts=item.get('segments',[item['synthesis_text']]);parts=[];segment_report=[]
  started=time.perf_counter()
  for index,text in enumerate(texts,1):
   torch.manual_seed(item['seed'])
   kwargs=dict(reference_wav_path=str(reference),cfg_value=plan['cfg'],inference_timesteps=item['steps'],denoise=False,normalize=False)
   for option in ('min_len','max_len'):
    if option in item:kwargs[option]=int(item[option])
   if item['mode'] in ('calm-continuation','styled-continuation'):
    kwargs.update(prompt_wav_path=str(prompt),prompt_text=item['prompt_text'])
   if item['mode'] != 'calm-continuation':
    text=item['style']+' '+text
   audio=model.generate(text=text,**kwargs)
   assert len(audio)>sr/2 and np.isfinite(audio).all()
   parts.append(audio)
   segment_report.append(dict(text=text,seconds=len(audio)/sr))
   if index<len(texts):parts.append(np.zeros(int(sr*item.get('additional_sentence_pause_seconds',0)),dtype=np.float32))
  audio=np.concatenate(parts)
  sf.write(raw,audio,sr,subtype='PCM_24')
  filtered=sosfiltfilt(butter(2,[70,9500],btype='bandpass',fs=sr,output='sos'),audio)
  filtered=filtered/np.max(np.abs(filtered))*0.85
  sf.write(clean,filtered,sr,subtype='PCM_24')
  report.append(dict(**item,cfg=plan['cfg'],sample_rate=sr,seconds=len(audio)/sr,inference_seconds=time.perf_counter()-started,reference_sha256=sha(reference),prompt_wav_sha256=sha(prompt),raw=raw.name,clean=clean.name,raw_sha256=sha(raw),clean_sha256=sha(clean),segments_generated=segment_report,status='awaiting user review; correction intent not listening verification',processing='Butterworth order 2 bandpass 70-9500Hz sosfiltfilt peak 0.85 PCM24'))
  report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print('DONE',item['number'],item['key'],len(audio)/sr,flush=True)
 print('COMPLETE',len(report),flush=True)

if __name__=='__main__':main()
