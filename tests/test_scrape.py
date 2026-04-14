import os
import pytest
from tools.scrape_comments import load_channels


def test_load_channels():
    channels = load_channels("config/channels.json")
    assert isinstance(channels, list)
    assert len(channels) >= 1
    assert "id" in channels[0]
    assert "name" in channels[0]
    assert "handle" in channels[0]
