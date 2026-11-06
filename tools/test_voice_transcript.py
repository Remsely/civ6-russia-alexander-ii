"""Guard language-aware checks of complete loading narration."""
from check_voice_transcript import compare_transcript


def test_complete_english_is_not_rejected_as_foreign_text():
    text = "Let reform strengthen the state, and peace give your subjects time to build."
    assert compare_transcript(text, text, 'en')['content_matches']


def test_cut_english_ending_is_rejected():
    assert not compare_transcript('Give your subjects time to build.', 'Give your subjects time to', 'en')['ending_matches']


def test_wrong_language_is_rejected_even_when_the_ending_matches():
    text = 'Give your subjects time to build.'
    result = compare_transcript(text, 'Привет. ' + text, 'en')
    assert result['unexpected_foreign_words'] and not result['content_matches']


def test_russian_still_rejects_spoken_english_style_instructions():
    text = 'Пусть мир даст вашим подданным время созидать.'
    assert compare_transcript(text, text)['content_matches']
    assert not compare_transcript(text, 'A stately narrator. ' + text)['content_matches']


def test_spoken_english_style_prefix_is_rejected():
    text = 'Welcome to the Winter Palace, Emperor Alexander. Give your subjects time to build.'
    assert not compare_transcript(text, 'A stately narrator speaks English. ' + text, 'en')['content_matches']
