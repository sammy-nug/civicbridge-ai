"""Language support: which languages exist, how far they are trusted, and output checks.

Translation here is treated as something that can fail. Every translated answer is checked,
and on failure the user gets the English answer with an honest notice. No Nigerian language has
passed human evaluation yet, and the API and UI say so until a reviewer signs it off here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.services.llm import LLMError, generate_json
from app.services.prompts import TRANSLATE_SYSTEM


@dataclass(frozen=True)
class Language:
    code: str
    english_name: str
    native_name: str
    human_reviewed: bool
    orthography_note: str = ""


LANGUAGES = {
    "en": Language("en", "English", "English", True),
    "ha": Language("ha", "Hausa", "Hausa", False, ", using standard Hausa spelling with hooked letters (ɓ, ɗ, ƙ)"),
    "yo": Language("yo", "Yoruba", "Yorùbá", False, ", using standard Yoruba spelling with subdots (ẹ, ọ, ṣ) and tone marks"),
    "ig": Language("ig", "Igbo", "Igbo", False, ", using standard Igbo spelling with subdots (ị, ọ, ụ)"),
}

# Common words, used only as a sanity check that output is in the expected language.
FUNCTION_WORDS = {
    "en": {"the", "and", "of", "to", "is", "you", "in", "for", "that", "are", "must", "can", "with"},
    "ha": {"da", "ne", "ce", "na", "a", "ka", "ku", "don", "zai", "ba", "za", "kuma", "ko", "shi", "ta", "su", "wannan", "domin", "kan", "cikin", "ya", "yana", "idan", "dole"},
    "yo": {"ni", "ti", "àwọn", "awọn", "láti", "lati", "sí", "si", "fún", "fun", "kan", "àti", "ati", "o", "ó", "rẹ", "pé", "pe", "ní", "lórí", "lori", "kí", "ki", "yìí", "yii", "gbọdọ̀", "gbọdọ", "bí", "bi", "tí", "kò", "ko"},
    "ig": {"na", "nke", "ga", "ma", "gị", "gi", "ndị", "ndi", "bụ", "bu", "ka", "maka", "ọ", "o", "a", "i", "ị", "dị", "di", "n'ime", "nwere", "ike", "site", "mgbe", "ya", "ha", "ahụ", "ahu"},
}
MIN_TARGET_WORD_RATIO = 0.12
MAX_ENGLISH_WORD_RATIO = 0.22

# Fixed messages. The non-English text was drafted without human review; see docs/responsible_ai.md.
MESSAGES = {
    "abstain": {
        "en": "I could not find enough information in the official sources available to me to answer this reliably, so I won't guess. Please check INEC's website (inecnigeria.org) or your nearest INEC office.",
        "ha": "Ban sami isassun bayanai a cikin takardun hukuma da nake da su ba don in amsa wannan tambaya da tabbaci, don haka ba zan yi hasashe ba. Da fatan za a duba shafin INEC (inecnigeria.org) ko ofishin INEC mafi kusa.",
        "yo": "Mi ò rí àlàyé tó tó nínú àwọn ìwé ìjọba tí mo ní láti dáhùn èyí pẹ̀lú ìdánilójú, nítorí náà mi ò ní fi àmọ̀ràn dáhùn. Ẹ jọ̀wọ́ ẹ wo ojú òpó INEC (inecnigeria.org) tàbí ọ́fíìsì INEC tó sún mọ́ yín jù.",
        "ig": "Achọtaghị m ozi zuru oke n'akwụkwọ gọọmentị m nwere iji zaa ajụjụ a n'ụzọ a pụrụ ịtụkwasị obi, ya mere agaghị m eche echiche. Biko lelee weebụsaịtị INEC (inecnigeria.org) ma ọ bụ ụlọ ọrụ INEC kacha nso gị.",
    },
    "partisan": {
        "en": "I can't recommend or compare candidates or parties. That choice is yours. I can explain how voting works, how to prepare for election day, and where to find official information.",
        "ha": "Ba zan iya ba da shawarar ɗan takara ko jam'iyya ko kwatanta su ba. Zaɓin naka ne. Zan iya bayyana yadda ake zaɓe, yadda za a shirya don ranar zaɓe, da inda za a sami bayanan hukuma.",
        "yo": "Mi ò lè dábàá tàbí fi àwọn olùdíje tàbí ẹgbẹ́ òṣèlú wéra. Ìpinnu yẹn jẹ́ tìrẹ. Mo lè ṣàlàyé bí a ṣe ń dìbò, bí a ṣe ń múra sílẹ̀ fún ọjọ́ ìdìbò, àti ibi tí a ti lè rí àlàyé ìjọba.",
        "ig": "Enweghị m ike ịtụ aro ma ọ bụ tụnyere ndị na-azọ ọkwa ma ọ bụ otu ndọrọ ndọrọ ọchịchị. Mkpebi ahụ bụ nke gị. Enwere m ike ịkọwa otú e si atụ vootu, otú e si akwado maka ụbọchị ntuli aka, na ebe a ga-achọta ozi gọọmentị.",
    },
    "prediction": {
        "en": "I don't predict election results. Results are announced by INEC after votes are counted and collated. I can explain how counting and collation work.",
        "ha": "Ba na hasashen sakamakon zaɓe. INEC ce ke sanar da sakamako bayan an ƙirga kuri'u an kuma tattara su. Zan iya bayyana yadda ake ƙirga da tattara kuri'u.",
        "yo": "Mi ò kìí sọ àsọtẹ́lẹ̀ èsì ìdìbò. INEC ló ń kéde èsì lẹ́yìn tí wọ́n bá ka ìbò tí wọ́n sì ṣàkójọ wọn. Mo lè ṣàlàyé bí a ṣe ń ka ìbò àti bí a ṣe ń ṣàkójọ wọn.",
        "ig": "Anaghị m ebu amụma maka nsonaazụ ntuli aka. INEC na-ekwupụta nsonaazụ mgbe a gụchara vootu ma chịkọta ha. Enwere m ike ịkọwa otú e si agụ na ịchịkọta vootu.",
    },
    "off_topic": {
        "en": "I can only help with electoral and civic information about Nigeria, such as voting, PVCs, election rules and observers.",
        "ha": "Zan iya taimakawa ne kawai da bayanai game da zaɓe da al'amuran jama'a a Najeriya, kamar kaɗa kuri'a, PVC, dokokin zaɓe da masu sa ido.",
        "yo": "Àlàyé nípa ìdìbò àti ọ̀rọ̀ ìlú ní Nàìjíríà nìkan ni mo lè ràn yín lọ́wọ́ lórí, bíi ìdìbò, PVC, òfin ìdìbò àti àwọn alákíyèsí.",
        "ig": "Naanị ozi gbasara ntuli aka na ihe gbasara obodo na Naịjirịa ka m nwere ike inyere gị aka, dịka ịtụ vootu, PVC, iwu ntuli aka na ndị na-ekiri ntuli aka.",
    },
    "sensitive_removed": {
        "en": "For your safety, I removed personal details from your message and did not use or save them. Please never share your PVC number, NIN or passwords here.",
        "ha": "Don tsaron ka, na cire bayanan sirri daga saƙonka ban yi amfani da su ko adana su ba. Don Allah kada ka taɓa raba lambar PVC, NIN ko kalmar sirri a nan.",
        "yo": "Fún ààbò yín, mo yọ àwọn àlàyé ti ara ẹni kúrò nínú ọ̀rọ̀ yín, mi ò lò wọ́n, mi ò sì tọ́jú wọn. Ẹ jọ̀wọ́ ẹ má ṣe pín nọ́mbà PVC, NIN tàbí ọ̀rọ̀ ìgbaniwọlé yín níbí.",
        "ig": "Maka nchekwa gị, ewepụla m ozi nkeonwe na ozi gị, ejighị m ha mee ihe, echekwaghị m ha. Biko ekesala nọmba PVC gị, NIN ma ọ bụ okwuntughe ebe a.",
    },
    "language_fallback": {
        "en": "",
        "ha": "Ba mu iya tabbatar da fassarar Hausa ta wannan amsa ba, don haka ga ta da Turanci.",
        "yo": "A kò lè fìdí ìtumọ̀ Yorùbá ìdáhùn yìí múlẹ̀, nítorí náà a fi Gẹ̀ẹ́sì kọ ọ́.",
        "ig": "Anyị enweghị ike ịkwado ntụgharị Igbo nke azịza a, ya mere ọ dị n'asụsụ Bekee.",
    },
    "language_unavailable": {
        "en": "I could not process this message right now. Please try again.",
        "ha": "Ba mu iya fahimtar wannan saƙo da tabbaci a yanzu ba. Don Allah a sake gwadawa ko a yi amfani da Turanci.",
        "yo": "A kò lè lóye ọ̀rọ̀ yìí pẹ̀lú ìdánilójú báyìí. Ẹ jọ̀wọ́ ẹ tún gbìyànjú tàbí kí ẹ lo Gẹ̀ẹ́sì.",
        "ig": "Anyị enweghị ike ịghọta ozi a n'ụzọ a pụrụ ịtụkwasị obi ugbu a. Biko nwaa ọzọ ma ọ bụ jiri Bekee.",
    },
}


def message(key: str, language: str) -> str:
    return MESSAGES[key].get(language) or MESSAGES[key]["en"]


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", text.lower())


def word_ratio(text: str, language: str) -> float:
    words = _words(text)
    if not words:
        return 0.0
    vocabulary = FUNCTION_WORDS[language]
    return sum(1 for word in words if word in vocabulary) / len(words)


def looks_like_language(text: str, language: str) -> bool:
    """A cheap sanity check. It catches obvious failures; it does not prove translation quality."""
    if language == "en":
        return True
    return word_ratio(text, language) >= MIN_TARGET_WORD_RATIO and word_ratio(text, "en") <= MAX_ENGLISH_WORD_RATIO


def find_translation_problems(source: str, translated: str, language: str) -> list[str]:
    """Check what can be checked automatically: markers, numbers and apparent language."""
    problems = []
    markers = lambda text: sorted(set(re.findall(r"\[\d+\]", text)))
    numbers = lambda text: set(re.findall(r"\d+(?:[.,:]\d+)*", re.sub(r"\[\d+\]", " ", text)))
    if markers(source) != markers(translated):
        problems.append("citation markers changed")
    missing = numbers(source) - numbers(translated)
    if missing:
        problems.append(f"numbers missing: {sorted(missing)}")
    if not looks_like_language(translated, language):
        problems.append("output does not look like the requested language")
    return problems


def translate_texts(texts: list[str], language: str) -> list[str] | None:
    """Translate a list of strings together. Returns None if any check fails."""
    if language == "en":
        return texts
    settings = LANGUAGES[language]
    system = TRANSLATE_SYSTEM.format(language=settings.english_name, orthography_note=settings.orthography_note)
    try:
        result = generate_json(system, "Input strings (JSON list):\n" + json.dumps(texts, ensure_ascii=False))
    except LLMError:
        return None
    translated = result.get("translation")
    if not isinstance(translated, list) or len(translated) != len(texts) or not all(isinstance(t, str) for t in translated):
        return None
    if find_translation_problems("\n".join(texts), "\n".join(translated), language):
        return None
    return translated
