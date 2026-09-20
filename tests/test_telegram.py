from geo_watcher.analysis import analyze
from geo_watcher.report import CheckKind, Family, Observation, Source
from geo_watcher.telegram import MAX_LENGTH, _has_degradation, format_html


def _country(check_id: str, value: str) -> Observation:
    return Observation(
        source=Source.SERVICES,
        id=check_id,
        name=f"<{check_id}>",
        kind=CheckKind.COUNTRY,
        family=Family.IPV4,
        value=value,
    )


def _stash(check_id: str, value: str) -> Observation:
    return Observation(
        source=Source.STASH,
        id=check_id,
        name=check_id,
        kind=CheckKind.AVAILABILITY,
        family=None,
        value=value,
    )


def test_country_change_renders_flags_and_escapes_names():
    google = _country("google", "RU")
    result = analyze("nl & co", [google], {google.key: "NL"})

    html = format_html(result)

    assert "nl &amp; co" in html
    assert "&lt;google&gt;" in html
    assert "🇳🇱 NL" in html
    assert "<mark>🇷🇺 RU</mark>" in html
    assert "<h4>🌍 География</h4>" in html
    assert "<h4>📺 Доступность</h4>" not in html


def test_degradation_and_recovery_are_told_apart():
    broke = _stash("chatgpt_web", "blocked")
    fixed = _stash("netflix_access", "available")

    degraded = analyze("nl-1", [broke], {broke.key: "available"})
    recovered = analyze("nl-1", [fixed], {fixed.key: "blocked"})

    assert _has_degradation(degraded.changes)
    assert not _has_degradation(recovered.changes)
    assert "🔴" in format_html(degraded)
    assert "🟢" in format_html(recovered)


def test_blocked_kind_is_inverted():
    captcha = Observation(
        source=Source.SERVICES,
        id="google_captcha",
        name="Google Search captcha",
        kind=CheckKind.BLOCKED,
        family=Family.IPV4,
        value="yes",
    )

    result = analyze("nl-1", [captcha], {captcha.key: "no"})

    assert _has_degradation(result.changes)


def test_snapshot_is_dropped_when_message_is_too_long():
    observations = [_country(f"s{i}", "RU") for i in range(4000)]
    previous = {o.key: "NL" for o in observations}

    html = format_html(analyze("nl-1", observations, previous))

    assert len(html) <= MAX_LENGTH
    assert "<details>" not in html
