"""Speech bindings shared by the asset generator and the audio builder."""
from pathlib import Path
import wave
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ROOT / 'art/voice/selected'
BANK = 'REMSELY_AlexanderII_Speech'
STOP = 'Stop_REMSELY_AlexanderII_Speech'
# Vanilla LeaderSpeech mixer, read from Base Speech.bnk (Stop_Leader_Speech target).
LEADER_SPEECH = 854467727
GAIN_DB = 1.0
SCENE_TAIL = 0.35
LINES = {
    'FIRST_MEET': ('first-meet-clean.wav', 'Play_RUSS_PA_FIRST_MEET_J_Edited'),
    'DECLARE_WAR_FROM_AI': ('declare-war-ai-clean.wav', 'Play_RUSS_PA_DECLARE_WAR_FROM_AI_Edited'),
    'KUDOS': ('kudos-clean.wav', 'Play_RUSS_PA_KUDOS_A'),
    'WARNING': ('warning-clean.wav', 'Play_RUSS_PA_WARNING_F_1'),
    'DEFEAT': ('defeat-ai-clean.wav', 'Play_RUSS_PA_DEFEAT_C'),
    'DECLARE_WAR_FROM_HUMAN': ('declare-war-human-clean.wav', 'Play_RUSS_PA_DECLARE_WAR_FROM_HUMAN_B_Edited'),
}


def event(slot):
    return 'Play_REMSELY_AlexanderII_' + slot


def bind_scene(tree):
    """Bind the six selected speech recordings and their cinematic durations."""
    replacements = {old: event(slot) for slot, (_, old) in LINES.items()}
    for trigger in list(tree.iter('Element')):
        fx = trigger.find('m_FXName')
        if fx is None:
            continue
        name = fx.get('text')
        if name in replacements:
            fx.set('text', replacements[name])
    # Cooker uses the animation binding's duration, even with an explicit timeline
    # duration. Give speech slots separate ANM descriptions of the same FGX motion.
    for timeline in tree.findall('.//m_Timelines/Element'):
        for slot in LINES:
            trigger = next(
                (t for t in timeline.findall('m_Triggers/Element')
                 if t.find('m_FXName').get('text') == event(slot)), None)
            if trigger is None and slot == 'DECLARE_WAR_FROM_HUMAN' and timeline.find('m_Name').get('text') == '02_DECLARE_WAR_FROM_HUMAN':
                # Earlier prototypes removed this unrecorded Peter trigger. Restore
                # its native 0.4s offset when upgrading an existing scene.
                prototype = next(t for t in tree.findall('.//m_Triggers/Element')
                                 if t.find('m_FXName').get('text') == event('FIRST_MEET'))
                trigger = etree.fromstring(etree.tostring(prototype))
                trigger.find('m_FXName').set('text', event(slot))
                trigger.find('m_Name').set('text', 'REMSELY_Speech')
                trigger.find('m_fStartTime').text = '0.400000'
                timeline.find('m_Triggers').insert(0, trigger)
            if trigger is None:
                continue
            duration = scene_duration(slot, trigger)
            timeline.find('m_fDuration').text = f'{duration:.6f}'
            animation = 'AlexanderII_Voice_' + slot
            timeline.find('m_AnimationName').set('text', animation)
            timeline_name = timeline.find('m_Name').get('text')
            for binding in tree.findall('.//m_animationBindings/m_Bindings/Element'):
                if binding.find('m_SlotName').get('text') == timeline_name:
                    binding.find('m_AnimationName').set('text', animation)
            description = etree.parse(str(ROOT / 'mod/Animations/AlexanderII_Idle.anm'))
            description.find('m_Name').set('text', animation)
            description.find('.//m_RelativePath').set('text', animation + '.fgx')
            description.find('m_fDuration').text = f'{duration:.6f}'
            description.write(str(ROOT / 'mod/Animations' / (animation + '.anm')),
                              encoding='utf-8', xml_declaration=True, pretty_print=True)
            for other in list(timeline.find('m_Triggers')):
                if float(other.findtext('m_fStartTime')) >= duration:
                    timeline.find('m_Triggers').remove(other)


def scene_duration(slot, trigger):
    """End the cinematic shortly after speech, rather than after the 16s idle."""
    with wave.open(str(SELECTED / LINES[slot][0])) as recording:
        seconds = recording.getnframes() / recording.getframerate()
    return float(trigger.findtext('m_fStartTime')) + seconds + SCENE_TAIL
