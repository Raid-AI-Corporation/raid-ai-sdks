"""Live smoke test against a real Raid AI tier.

Skipped unless RAID_API_KEY and RAID_API_BASE_URL are set, so it never breaks CI. To run it:

    RAID_API_KEY=<your-api-key> \
    RAID_API_BASE_URL=<raid-ai-api-url> \
    pytest tests/test_live_smoke.py
"""

from __future__ import annotations

import base64
import os

import pytest

from raidxai import FileInput, RaidClient

API_KEY = os.environ.get("RAID_API_KEY")
BASE_URL = os.environ.get("RAID_API_BASE_URL")
# Opt-in: path to a short speech clip. Audio detection costs credits, so it never runs by default.
AUDIO_PATH = os.environ.get("RAID_SMOKE_AUDIO_PATH")

# A 1×1 transparent PNG.
ONE_PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.mark.skipif(not (API_KEY and BASE_URL), reason="RAID_API_KEY / RAID_API_BASE_URL not set")
def test_images_process_live():
    with RaidClient(api_key=API_KEY, base_url=BASE_URL, timeout=120.0) as raid:
        res = raid.images.process(
            FileInput(data=ONE_PX_PNG, file_name="smoke.png", content_type="image/png")
        )
    assert res.images is not None


@pytest.mark.skipif(
    not (API_KEY and BASE_URL and AUDIO_PATH),
    reason="RAID_API_KEY / RAID_API_BASE_URL / RAID_SMOKE_AUDIO_PATH not set",
)
def test_audio_process_live():
    with RaidClient(api_key=API_KEY, base_url=BASE_URL, timeout=300.0) as raid:
        res = raid.audio.process(FileInput.from_path(AUDIO_PATH))
    assert isinstance(res.workflow_type, str)
    if res.is_successful and res.metadata is not None:
        if res.metadata.provider is not None:
            assert isinstance(res.metadata.provider, str)
        if res.metadata.score is not None:
            assert 0.0 <= res.metadata.score <= 1.0
