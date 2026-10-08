import os
from datetime import UTC, datetime

import pytest
from mnemos.media import VideoFrame
from mnemos.vision import YOLOXProvider, YuNetProvider


def frame(format="bgr24"):
    return VideoFrame("safe", 0, 0, datetime.now(UTC), 320, 240, format, bytes(320 * 240 * 3))


def test_unsupported_pixels_rejected_before_loading():
    for provider in [YOLOXProvider(), YuNetProvider()]:
        with pytest.raises(ValueError):
            provider.detect(frame("rgb24"))
        assert provider.model is None


@pytest.mark.skipif(
    not os.environ.get("MNEMOS_TEST_MODELS"), reason="real model integration opt-in"
)
def test_real_models_empty_scene_and_eviction():
    for provider in [YOLOXProvider(), YuNetProvider()]:
        assert provider.detect(frame()) == []
        assert provider.model is not None
        provider.unload()
        assert provider.model is None


@pytest.mark.skipif(
    not os.environ.get("MNEMOS_TEST_MODELS"), reason="actual perception replay opt-in"
)
def test_actual_perception_av_replay():
    from mnemos.perception_replay import main

    main()
