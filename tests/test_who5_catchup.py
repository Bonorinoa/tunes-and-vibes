"""Tests for scripts/who5_catchup.sh (Monday WHO-5 catch-up): silent when answered, reminder when missing."""
import pathlib
import sqlite3
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "who5_catchup.sh"


def run(tmp_path, rows, today="2026-10-19"):
    db = tmp_path / "panel.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE survey (week_start TEXT PRIMARY KEY, responded_at TEXT, raw_total INTEGER)")
    con.executemany("INSERT INTO survey VALUES (?, ?, ?)", rows)
    con.commit()
    con.close()
    survey = tmp_path / "survey.sh"
    survey.write_text("echo SURVEY-TEXT\n")
    env = {"TV_DB": str(db), "TV_SURVEY_SCRIPT": str(survey), "TV_TODAY": today, "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)


def test_silent_when_last_week_answered(tmp_path):
    r = run(tmp_path, [("2026-10-12", "2026-10-18T17:00:00+00:00", 20)])
    assert r.returncode == 0
    assert r.stdout == ""


def test_reminder_and_survey_when_missing(tmp_path):
    r = run(tmp_path, [("2026-10-05", "2026-10-12T17:36:21+00:00", 21)])
    assert r.returncode == 0
    assert "week of 2026-10-12" in r.stdout
    assert "SURVEY-TEXT" in r.stdout


def test_unreadable_db_is_loud(tmp_path):
    env = {"TV_DB": str(tmp_path / "missing" / "x.sqlite"), "TV_TODAY": "2026-10-19", "PATH": "/usr/bin:/bin",
           "HOME": str(tmp_path)}  # cron always sets HOME
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
    assert "could not read" in r.stdout
