import pytest

from geo_watcher.exclusions import CheckExclusions
from geo_watcher.report import CheckKind, Observation, Source

EXCLUSIONS = CheckExclusions(
    {
        "nl-*": ["netflix_access"],
        "nl-1": ["Google"],
        "de-1": ["YouTube*", "ChatGPT (web)"],
    },
)


def _observation(check_id: str, name: str) -> Observation:
    return Observation(
        source=Source.SERVICES,
        id=check_id,
        name=name,
        kind=CheckKind.COUNTRY,
        family=None,
        value="NL",
    )


@pytest.mark.parametrize(
    ("node_name", "check_id", "check_name", "excluded"),
    [
        ("nl-1", "netflix_access", "Netflix", True),
        ("nl-1", "google", "Google", True),
        ("nl-2", "google", "Google", False),
        ("nl-2", "netflix_access", "Netflix", True),
        ("de-1", "youtube", "YouTube", True),
        ("de-1", "youtube_premium_access", "YouTube Premium", True),
        ("de-1", "netflix_access", "Netflix", False),
        ("de-1", "chatgpt_web", "ChatGPT (web)", True),
        ("NL-1", "netflix_access", "Netflix", False),
    ],
)
def test_excludes_by_id_or_name(
    node_name: str,
    check_id: str,
    check_name: str,
    *,
    excluded: bool,
):
    observation = _observation(check_id, check_name)

    assert EXCLUSIONS.excludes(node_name, observation) is excluded


def test_apply_drops_excluded_observations():
    google = _observation("google", "Google")
    netflix = _observation("netflix_access", "Netflix")

    assert EXCLUSIONS.apply("nl-2", [google, netflix]) == [google]


def test_no_rules_exclude_nothing():
    observation = _observation("google", "Google")

    assert not CheckExclusions().excludes("nl-1", observation)
