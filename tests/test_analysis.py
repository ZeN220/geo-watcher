from geo_watcher.analysis import analyze, merge_state
from geo_watcher.report import (
    CheckKind,
    Source,
    StashState,
    load_report,
    parse_observations,
)

REPORT = load_report(
    {
        "schema": 1,
        "geo": {
            "services": [
                {
                    "id": "google",
                    "name": "Google",
                    "kind": "country",
                    "ipv4": {"value": "RU", "country": "Russia"},
                    "ipv6": {"error": "no ipv6"},
                },
                {
                    "id": "youtube",
                    "name": "YouTube",
                    "kind": "country",
                    "ipv4": {"value": "nl", "country": "Netherlands"},
                },
                {
                    "id": "google_captcha",
                    "name": "Google Search captcha",
                    "kind": "blocked",
                    "ipv4": {"value": "No"},
                },
                {
                    "id": "reddit_guest",
                    "name": "Reddit guest access",
                    "kind": "availability",
                    "ipv4": {"error": "request failed"},
                },
            ],
            "geoip": [
                {
                    "id": "maxmind",
                    "name": "MaxMind",
                    "kind": "country",
                    "ipv4": {"value": "NL"},
                },
            ],
            "cdn": [
                {
                    "id": "cloudflare",
                    "name": "Cloudflare",
                    "kind": "country",
                    "ipv4": {"value": "DE"},
                },
            ],
        },
        "stash_checks": [
            {
                "id": "netflix_access",
                "name": "Netflix",
                "state": "restricted",
                "region": "us",
                "detail": "Originals only",
                "rtt_ms": 120.5,
            },
            {"id": "chatgpt_web", "name": "ChatGPT (web)", "state": "blocked"},
            {
                "id": "youtube_premium_access",
                "name": "YouTube Premium",
                "state": "error",
                "error": "request failed",
            },
        ],
    }
)


def test_parse_skips_errors_and_unselected_sources():
    observations = parse_observations(REPORT, [Source.SERVICES, Source.GEOIP])

    assert {(o.id, o.family, o.value) for o in observations} == {
        ("google", "ipv4", "RU"),
        ("youtube", "ipv4", "NL"),
        ("google_captcha", "ipv4", "no"),
        ("maxmind", "ipv4", "NL"),
    }


def test_parse_stash_checks_keeps_region_and_skips_errors():
    observations = parse_observations(REPORT, [Source.STASH])

    assert [(o.key, o.label, o.value) for o in observations] == [
        ("stash/netflix_access", "Netflix (stash)", "restricted (US)"),
        ("stash/chatgpt_web", "ChatGPT (web) (stash)", "blocked"),
    ]


def test_parse_report_without_geo():
    report = load_report({"schema": 1, "findings": []})

    assert parse_observations(report, [Source.SERVICES, Source.STASH]) == []


def test_load_report_accepts_null_lists_and_ignores_other_sections():
    report = load_report(
        {
            "schema": 1,
            "identity": {"ipv4": "203.0.113.1", "asn": 64500},
            "connectivity": {"targets": []},
            "geo": {"services": None, "geoip": None, "cdn": None},
            "stash_checks": None,
        },
    )

    assert report.geo is not None
    assert report.geo.group(Source.SERVICES) == []
    assert report.stash_checks == []
    assert parse_observations(report, list(Source)) == []


def test_load_report_falls_back_on_unknown_kind_and_state():
    report = load_report(
        {
            "schema": 1,
            "geo": {
                "services": [
                    {
                        "id": "whatever",
                        "name": "Whatever",
                        "kind": "latency",
                        "ipv4": {"value": "fast"},
                    },
                ],
            },
            "stash_checks": [
                {"id": "hulu", "name": "Hulu", "state": "maybe"},
            ],
        },
    )

    assert report.geo is not None
    assert report.geo.group(Source.SERVICES)[0].kind is CheckKind.UNKNOWN
    assert report.stash_checks[0].state is StashState.UNKNOWN
    observations = parse_observations(report, [Source.SERVICES, Source.STASH])
    assert [(o.id, o.value) for o in observations] == [
        ("whatever", "fast"),
        ("hulu", "unknown"),
    ]


def test_analyze_changes():
    observations = parse_observations(REPORT, [Source.SERVICES, Source.STASH])
    previous = {
        "services/google/ipv4": "NL",
        "services/youtube/ipv4": "NL",
        "stash/chatgpt_web": "available",
    }

    result = analyze("nl-1", observations, previous)

    assert [
        (c.observation.id, c.previous, c.current) for c in result.changes
    ] == [
        ("google", "NL", "RU"),
        ("chatgpt_web", "available", "blocked"),
    ]


def test_analyze_first_check_has_no_changes():
    observations = parse_observations(REPORT, [Source.SERVICES, Source.STASH])

    assert analyze("nl-1", observations, {}).changes == []


def test_merge_state_keeps_checks_missing_this_run():
    observations = parse_observations(REPORT, [Source.STASH])
    previous = {
        "stash/youtube_premium_access": "available",
        "stash/chatgpt_web": "available",
    }

    state = merge_state(previous, observations)

    assert state == {
        "stash/youtube_premium_access": "available",
        "stash/chatgpt_web": "blocked",
        "stash/netflix_access": "restricted (US)",
    }
