from app.services.language import LANGUAGES, MESSAGES, find_translation_problems, looks_like_language

HAUSA = "Dole ne ka je ofishin INEC don neman PVC, kuma za a ba ka sabon kati kafin ranar zaɓe [1]."
YORUBA = "O gbọ́dọ̀ lọ sí ọ́fíìsì INEC láti béèrè fún PVC, àti pé wọn ó fún ọ ní káàdì tuntun [1]."
IGBO = "Ị ga-aga n'ụlọ ọrụ INEC ka ị rịọ maka PVC, ma a ga-enye gị kaadị ọhụrụ na mgbe ahụ [1]."
ENGLISH = "You must go to the INEC office to apply for a PVC and you will be given a new card [1]."


def test_no_nigerian_language_is_marked_human_reviewed():
    # This must only change after a real human review, recorded in docs/responsible_ai.md.
    assert not any(LANGUAGES[code].human_reviewed for code in ("ha", "yo", "ig"))


def test_real_language_samples_pass():
    assert looks_like_language(HAUSA, "ha")
    assert looks_like_language(YORUBA, "yo")
    assert looks_like_language(IGBO, "ig")


def test_english_passed_off_as_translation_fails():
    for code in ("ha", "yo", "ig"):
        assert not looks_like_language(ENGLISH, code)


def test_dropped_marker_or_number_is_detected():
    source = "Apply 90 days before polling day [1]."
    assert any("citation" in p for p in find_translation_problems(source, "Dole ne ka nema kwanaki 90 kafin ranar zaɓe.", "ha"))
    assert any("numbers" in p for p in find_translation_problems(source, "Dole ne ka nema kafin ranar zaɓe da kuma a cikin kwanaki [1].", "ha"))
    assert find_translation_problems(source, "Dole ne ka nema kwanaki 90 kafin ranar zaɓe [1].", "ha") == []


def test_every_fixed_message_exists_in_every_language():
    for key, translations in MESSAGES.items():
        assert set(translations) == {"en", "ha", "yo", "ig"}, key
