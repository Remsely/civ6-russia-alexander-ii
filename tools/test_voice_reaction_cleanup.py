"""Check that inherited Peter vocal reactions do not overlap new dialogue."""
from pathlib import Path

from lxml import etree

from leader_voice import PETER_VOCAL_REACTIONS, remove_peter_vocal_reactions


def test_reaction_cleanup_is_precise_and_idempotent():
    scene = etree.fromstring(b'''<Asset><m_Timelines><Element><m_Triggers>
        <Element><m_FXName text="RUSS_PA_Hmm_NeutralPositive"/></Element>
        <Element><m_FXName text="RUSS_PA_Ha_NeutralToNegative"/></Element>
        <Element><m_FXName text="RUSS_PA_Hmm_HappyPositive"/></Element>
        <Element><m_FXName text="RUSS_PA_Ha_HappyNegative"/></Element>
        <Element><m_FXName text="RUSS_PA_Breath_HappyToNeutral"/></Element>
        <Element><m_FXName text="RUSS_PA_Breath_NeutralToEnraged"/></Element>
        <Element><m_FXName text="RUSS_PA_Breath_UnhappyToEnraged"/></Element>
        <Element><m_FXName text="Leader_Foley_Cloth_Medium"/></Element>
        <Element><m_FXName text="Play_REMSELY_AlexanderII_FIRST_MEET"/></Element>
    </m_Triggers></Element></m_Timelines></Asset>''')
    assert remove_peter_vocal_reactions(scene) == 7
    assert [x.get('text') for x in scene.findall('.//m_FXName')] == [
        'Leader_Foley_Cloth_Medium', 'Play_REMSELY_AlexanderII_FIRST_MEET']
    assert remove_peter_vocal_reactions(scene) == 0


def test_current_scene_preserves_foley_and_has_no_removed_reactions():
    scene = etree.parse(str(Path('mod/Assets/AlexanderII.ast')))
    names = [x.get('text') for x in scene.findall('.//m_FXName')]
    assert not (set(names) & PETER_VOCAL_REACTIONS)
    assert not any(name and name.startswith('RUSS_PA_') for name in names)
    assert 'Leader_Foley_Cloth_Medium' in names
    assert 'Play_REMSELY_AlexanderII_FIRST_MEET' in names
