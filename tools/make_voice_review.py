"""Build a current listening catalog from game text and selected/candidate manifests."""
import json
from leader_voice import LINES
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
LABELS={
'ACCEPT_DECLARE_FRIEND_FROM_AI':'Игрок принял дружбу Александра',
'ACCEPT_DECLARE_FRIEND_FROM_HUMAN':'Александр принимает дружбу игрока',
'ACCEPT_DELEGATION_FROM_HUMAN':'Принятие делегации',
'ACCEPT_MAKE_DEAL_FROM_AI':'Игрок согласился на сделку',
'ACCEPT_OPEN_BORDERS_FROM_HUMAN':'Согласие открыть границы',
'DECLARE_FRIEND_FROM_AI':'Предложение дружбы',
'DECLARE_WAR_FROM_AI':'Александр объявляет войну',
'DECLARE_WAR_FROM_HUMAN':'Игрок объявляет войну Александру',
'DEFEAT_FROM_AI':'Поражение: империя пала',
'DEFEAT_FROM_HUMAN':'Поражение: вы одержали верх',
'DELEGATION_FROM_AI':'Отправка делегации',
'DENOUNCE_FROM_AI':'Осуждение игрока',
'DENOUNCE_FROM_HUMAN':'Ответ на осуждение',
'FIRST_MEET':'Первая встреча',
'FIRST_MEET_NEAR_INITIATOR_POSITIVE':'Благодарность за прием при первой встрече',
'FIRST_MEET_NO_MANS_INFO_EXCHANGE':'Обмен сведениями о странах',
'FIRST_MEET_VISIT_RECIPIENT':'Приглашение посетить город',
'GREETING':'Обычное приветствие',
'KUDO_EXIT':'Похвала за управление государством',
'MAKE_ALLIANCE_FROM_AI':'Предложение союза',
'MAKE_PEACE_AI_ACCEPT_DEAL':'Согласие на мир',
'MAKE_PEACE_AI_REFUSE_DEAL':'Отказ от условий мира',
'MAKE_PEACE_FROM_AI':'Предложение мира',
'OPEN_BORDERS_FROM_AI':'Просьба открыть границы',
'REJECT_DECLARE_FRIEND_FROM_AI':'Игрок отверг дружбу Александра',
'REJECT_DECLARE_FRIEND_FROM_HUMAN':'Александр отказывает в дружбе',
'REJECT_DELEGATION_FROM_HUMAN':'Отказ принять делегацию',
'REJECT_MAKE_DEAL_FROM_AI':'Отказ от сделки',
'REJECT_OPEN_BORDERS_FROM_HUMAN':'Отказ открыть границы',
'WARNING_EXIT':'Упрек за развязанную войну',
'WARNING_TOO_MANY_TROOPS_NEAR_ME':'Войска у границ',
}
selected={r['key']:r for r in json.loads((ROOT/'art/voice/selected/manifest.json').read_text(encoding='utf-8')) if r['file'].endswith('-clean.wav')}
candidates={r['key']:r for r in json.loads((ROOT/'art/voice/candidates/diplomacy-v1/manifest.json').read_text(encoding='utf-8'))}
latest_path=ROOT/'art/voice/candidates/review-round2/manifest.json'
latest={row['key']:row for row in json.loads(latest_path.read_text(encoding='utf-8'))} if latest_path.exists() else {}
round3_path=ROOT/'art/voice/candidates/review-round3/manifest.json'
round3={row['key']:row for row in json.loads(round3_path.read_text(encoding='utf-8'))} if round3_path.exists() else {}
round4_path=ROOT/'art/voice/candidates/review-round4/manifest.json'
round4={row['key']:row for row in json.loads(round4_path.read_text(encoding='utf-8'))} if round4_path.exists() else {}
round5_path=ROOT/'art/voice/candidates/review-round5/manifest.json'
round5={row['key']:row for row in json.loads(round5_path.read_text(encoding='utf-8'))} if round5_path.exists() else {}
trial={r['key']:r for r in json.loads((ROOT/'art/voice/game-trial-manifest.json').read_text(encoding='utf-8'))}
feedback=json.loads((ROOT/'art/voice/candidates/review-feedback.json').read_text(encoding='utf-8'))
page=['# Текущий список записей для прослушивания','', '31 дипломатическая реплика. Номера сохраняют порядок игровых XML. Новые дубли по последнему отзыву помечены отдельно: это пробы для оценки, а не подтверждение исправления.', '', 'Первая встреча: выбранные 32 шага. Ответ о дружбе №1: временный выбор, требует доработки. Прежние №7, 9, 19 и 30 сняты с окончательного одобрения по последнему отзыву; установленные WAV сохранены до выбора замен.', '']
scene_keys={('DEFEAT_FROM_AI' if k=='DEFEAT' else 'KUDO_EXIT' if k=='KUDOS' else 'WARNING_EXIT' if k=='WARNING' else k): filename for k,(filename,_) in LINES.items()}
count=0
for row in ET.parse(ROOT/'mod/Text/ru_RU.xml').getroot().iter('Replace'):
 tag=row.get('Tag','');suffix='_LEADER_REMSELY_ALEXANDER_II_ANY'
 if not(tag.startswith('LOC_DIPLO_') and tag.endswith(suffix)):continue
 key=tag[len('LOC_DIPLO_'):-len(suffix)]
 if key not in LABELS:raise ValueError(key)
 count+=1;text=row.findtext('Text').replace(' (Осуждает вас)','')
 if key in scene_keys:
  path=ROOT/'art/voice/selected'/scene_keys[key];state='подключен к кинематографической сцене; прежние замечания к качеству сохраняются'
 elif key in trial:
  item=trial[key];path=ROOT/item['file'];state='подключен к пробной сборке; воспроизведение в игре не проверено'
 elif key=='DENOUNCE_FROM_AI' and key in selected:
  item=selected[key];path=ROOT/'art/voice/selected'/item['file'];state='выбран пользователем; в игру не подключен'
 elif key in round5:
  item=round5[key];path=ROOT/'art/voice/candidates/review-round5'/item['clean'];state='новая проба по замечаниям, ожидает оценки; в игру не подключена'
 elif key in round4:
  item=round4[key];path=ROOT/'art/voice/candidates/review-round4'/item['clean'];state='новая проба по замечаниям, ожидает оценки; в игру не подключена'
 elif key in round3:
  item=round3[key];path=ROOT/'art/voice/candidates/review-round3'/item['clean'];state='новая проба по замечаниям, ожидает оценки; в игру не подключена'
 elif key in latest:
  item=latest[key];path=ROOT/'art/voice/candidates/review-round2'/item['clean'];state='новая проба по замечаниям, ожидает оценки; в игру не подключена'
 elif key in selected:
  item=selected[key];path=ROOT/'art/voice/selected'/item['file']
  state='временно выбран; требуется доработка, в игру не подключен' if item.get('status')=='provisional' else 'выбран и подключен'
 else:
  item=candidates[key];path=ROOT/'art/voice/candidates/diplomacy-v1'/item['clean'];state='проба, ожидает оценки; в игру не подключена'
 if key not in latest and key not in round3 and key not in round4 and key not in round5 and feedback.get(key,{}).get('needs_rework'):
  state+='; есть замечания, требуется переделка'
 assert path.is_file(),path
 note=feedback.get(key,{}).get('latest_feedback','')
 page += [f'## {count}. {LABELS[key]}', '',f'`{key}` — {state}.', '',text,'',f'![Прослушать]({path.as_posix()})','']
 if note:page += ['Последнее замечание: '+note+'.','']
assert count==31
from loading_voice import loading_recording
loading=loading_recording()
page += ['## 32. Русское вступление', '', loading['text'], '',
 f"![128 шагов, темп 88%]({(ROOT/loading['file']).as_posix()})", '',
 f"Сокращенная проба: {loading['seconds']:.2f} с, без фильтра, atempo 0.88. Распознаванием проверен текст; качество подачи, естественность концовки и последовательность в игре ожидают проверки. Штатная речь об эпохе сохранена перед обращением к лидеру. Прежний выбранный полный дубль сохранен в selected/.", '',
 'Архив предыдущих дублей: [история]('+str((ROOT/'art/voice/candidates/diplomacy-v1/review.md').as_posix())+').', '']
if loading.get('user_feedback'): page += ['Последний отзыв о текущем установленном дубле: '+loading['user_feedback'], '']
next_loading=feedback.get('LOADING_RU',{}).get('next_candidates')
if next_loading:
 candidate_dir=ROOT/'art/voice/candidates'/next_loading
 review_path=candidate_dir/'review.json'
 if review_path.exists():
  primary=json.loads(review_path.read_text(encoding='utf-8'))
  takes=[primary]+primary.get('alternatives',[])
  text_shown=False
  for index,take in enumerate(takes,1):
   # Preview eligibility is not an installation approval or a passed transcript check.
   if not (take.get('asr_content_matches') or take.get('listening_ready')): continue
   page += [f"Новая проба №32, вариант {index}, seed {take['seed']}; ожидает прослушивания, не установлена.", '',
    f"![{take['steps']} шагов, темп 88%, вариант {index}]({(candidate_dir/take['review_file']).as_posix()})", '',
    f"Длительность: {take['seconds']:.2f} с. {take.get('review_note_ru', '')} {take.get('transcript_note_ru', 'Распознаванием проверены слова; тембр, подача и естественная концовка оцениваются на слух.')}", '']
   if not text_shown and take['text'] != loading['text']:
    page += ['Текст новых проб: '+take['text'], ''];text_shown=True
(ROOT/'docs/voice-review.ru.md').write_text('\n'.join(page),encoding='utf-8')
print('Current catalog updated: 31 diplomatic entries + loading; English excluded')
