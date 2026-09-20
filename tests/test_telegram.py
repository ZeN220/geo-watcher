from geo_watcher.analysis import analyze
from geo_watcher.report import Family, Observation, Source
from geo_watcher.telegram import MAX_MESSAGE_LENGTH, format_message


def _observation(check_id: str, value: str) -> Observation:
    return Observation(
        source=Source.SERVICES,
        id=check_id,
        name=f"<{check_id}>",
        family=Family.IPV4,
        value=value,
    )


def test_format_message_escapes_and_lists_changes():
    google = _observation("google", "RU")
    result = analyze("nl & co", [google], {google.key: "NL"})

    text = format_message(result)

    assert "nl &amp; co" in text
    assert "&lt;google&gt;" in text
    assert "NL → <b>RU</b>" in text


def test_format_message_is_truncated():
    observations = [_observation(f"s{i}", "RU") for i in range(500)]
    previous = {o.key: "NL" for o in observations}

    text = format_message(analyze("nl-1", observations, previous))

    assert len(text) <= MAX_MESSAGE_LENGTH + 2
    assert text.endswith("…")
