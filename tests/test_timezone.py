import os
import textwrap
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from app.parsing import extract_date_dt, parse_date_field, localize_datetime, get_localized_now

def test_extract_date_dt_localized():
    # Naive date from YAML should be localized to the given timezone
    dt = extract_date_dt("2026-04-07", tz_name="America/New_York")
    assert dt.tzinfo == ZoneInfo("America/New_York")
    assert dt.hour == 0
    assert dt.minute == 0

def test_parse_date_field_localized():
    # Date string should be the same regardless of TZ for YYYY-MM-DD
    # because it's just February 01, 2025 at midnight in that TZ.
    fmt = parse_date_field("2026-04-07", tz_name="America/New_York")
    assert fmt == "April 07, 2026"

def test_localize_datetime_naive():
    # Naive datetime (like from mtime) should be treated as UTC then converted
    naive = datetime(2026, 4, 7, 12, 0, 0) # 12:00 UTC
    localized = localize_datetime(naive, tz_name="America/New_York")
    # America/New_York is UTC-4 in April (EDT)
    assert localized.hour == 8 
    assert localized.tzinfo == ZoneInfo("America/New_York")

def test_get_localized_now():
    now_ny = get_localized_now("America/New_York")
    assert now_ny.tzinfo == ZoneInfo("America/New_York")
    
    now_utc = get_localized_now("UTC")
    assert now_utc.tzinfo == ZoneInfo("UTC")

def test_invalid_timezone_fallback_to_utc():
    # Invalid TZ should fallback to UTC without crashing
    dt = extract_date_dt("2026-04-07", tz_name="Invalid/City")
    assert dt.tzinfo == timezone.utc
