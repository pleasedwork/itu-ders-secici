import json
from types import SimpleNamespace

import run
from request_manager import RequestManager


def test_read_inputs_parses_multiple_backup_crns(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "account": {"username": "student", "password": "password"},
                "courses": {
                    "crn": ["14150:14151:14152"],
                    "scrn": [],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run, "CONFIG_FILE_PATH", str(config_path))

    _, _, crn_list, scrn_list, backup_map, _ = run.read_inputs(test_mode=True)

    assert crn_list == ["14150"]
    assert scrn_list == []
    assert backup_map == {"14150": ["14151", "14152"]}


def test_quota_full_cycles_through_multiple_backup_crns(monkeypatch):
    result_codes = iter(
        [
            ("14150", "VAL06"),
            ("14151", "VAL06"),
            ("14152", "VAL06"),
        ]
    )

    def fake_post(*args, **kwargs):
        crn, result_code = next(result_codes)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "ecrnResultList": [{"crn": crn, "resultCode": result_code}],
                    "scrnResultList": [],
                }
            )
        )

    monkeypatch.setattr("request_manager.requests.post", fake_post)
    manager = RequestManager(
        "Bearer test-token",
        "https://obs.itu.edu.tr/select",
        "https://obs.itu.edu.tr/time",
        {"14150": ["14151", "14152"]},
    )
    crn_list = ["14150"]

    for expected_crn in ["14151", "14152", "14150"]:
        crn_list, _, timed_out = manager.request_course_selection(crn_list, [])
        assert crn_list == [expected_crn]
        assert timed_out is False


def test_request_manager_keeps_single_backup_compatibility(monkeypatch):
    monkeypatch.setattr(
        "request_manager.requests.post",
        lambda *args, **kwargs: SimpleNamespace(
            text=json.dumps(
                {
                    "ecrnResultList": [{"crn": "14150", "resultCode": "VAL06"}],
                    "scrnResultList": [],
                }
            )
        ),
    )
    manager = RequestManager(
        "Bearer test-token",
        "https://obs.itu.edu.tr/select",
        "https://obs.itu.edu.tr/time",
        {"14150": "14151"},
    )

    crn_list, _, timed_out = manager.request_course_selection(["14150"], [])

    assert crn_list == ["14151"]
    assert timed_out is False