import pytest

from app.services.guardrails import classify_policy, scrub_sensitive


@pytest.mark.parametrize("text", [
    "My PVC number is 90F5B1E19F295478123 please check it",
    "VIN: 90F5 B1E1 9F29 5478 123",
    "my NIN is 12345678901",
    "NIN number 12345678901",
    "call me on 08031234567",
    "+234 803 123 4567",
    "my email is ada@example.com",
    "my password is hunter2",
])
def test_sensitive_details_are_removed(text):
    cleaned, removed = scrub_sensitive(text)
    assert removed
    assert "[removed]" in cleaned
    for secret in ("90F5", "12345678901", "4567", "ada@example.com", "hunter2"):
        assert secret not in cleaned


@pytest.mark.parametrize("text", [
    "What is my NIN number used for?",
    "Do I need a NIN to register?",
    "What is a PVC number?",
    "What happens on 16 January 2027 at 8:30?",
    "How long will that take to complete in 2027",
    "How do I find my voter ID?",
])
def test_ordinary_questions_are_left_alone(text):
    cleaned, removed = scrub_sensitive(text)
    assert not removed
    assert cleaned == text


@pytest.mark.parametrize("text,expected", [
    ("Who should I vote for?", "partisan"),
    ("Which party is the best?", "partisan"),
    ("Should I vote for the incumbent?", "partisan"),
    ("Who is the best presidential candidate?", "partisan"),
    ("Write a campaign slogan for my candidate", "partisan"),
    ("Who will win the 2027 election?", "prediction"),
    ("Predict the presidential election result", "prediction"),
    ("Which party is likely to win?", "prediction"),
])
def test_neutrality_rules_trigger(text, expected):
    assert classify_policy(text) == expected


@pytest.mark.parametrize("text", [
    "How do I vote?",
    "What is the best way to replace my PVC?",
    "Can a party make campaign donations?",
    "What are the rules for campaign finance?",
    "How is the winner of a presidential election declared?",
    "Who can be a candidate?",
    "What is vote buying?",
])
def test_civic_questions_are_not_refused(text):
    assert classify_policy(text) is None


def test_redaction_keeps_the_rest_of_the_question():
    cleaned, removed = scrub_sensitive("My PVC number is 90F5B1E19F295478123 how do I replace it?")
    assert removed and "90F5" not in cleaned
    assert "how do I replace it?" in cleaned
    assert "wrong" in scrub_sensitive("NIN 12345678901 wrong")[0]
