from dataclasses import replace
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from mnemos.reference_quality import inspect_crop
from mnemos.references import ReferenceRow
from mnemos.storage import EntityRepository
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_references import fixture


def test_no_signal_rejects_but_plain_colored_objects_remain_reviewable():
    for value in (0, 1, 254, 255):
        with pytest.raises(ValueError, match="visual signal"):
            inspect_crop(np.full((64, 64, 3), value, dtype=np.uint8))
    plain = inspect_crop(np.full((64, 64, 3), [20, 90, 40], dtype=np.uint8))
    assert plain["warnings"] == ["low-contrast", "low-edge-detail"]
    assert plain["clipped_fraction"] == 0 and plain["version"] == 1


def test_detail_diagnostics_bounded_sampling_and_no_false_identity_claim():
    checker = ((np.indices((128, 128)).sum(axis=0) // 8) % 2 * 180 + 35).astype(np.uint8)
    sharp = np.repeat(checker[:, :, None], 3, axis=2)
    measured = inspect_crop(sharp)
    blurred = inspect_crop(cv2.GaussianBlur(sharp, (31, 31), 10))
    assert measured["edge_mean"] > blurred["edge_mean"]
    assert measured["contrast_std"] > blurred["contrast_std"]
    assert measured["warnings"] == []
    assert "low-edge-detail" in blurred["warnings"]
    large = inspect_crop(cv2.resize(sharp, (1600, 800)))
    assert (large["sample_width"], large["sample_height"]) == (256, 128)
    assert (large["width"], large["height"]) == (1600, 800)
    assert "confidence" not in measured and "identity" not in measured
    for bad in (
        np.zeros((10, 10, 3), np.uint8),
        np.zeros((64, 64)),
        np.zeros((64, 64, 3), np.float32),
    ):
        with pytest.raises(ValueError):
            inspect_crop(bad)


def test_no_signal_crop_never_creates_reference_and_multiple_quality_views_persist(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "quality.db"))
    service, entity, capture, track, _jpeg, _provenance = fixture(repo, tmp_path)
    original = capture.reference_frame
    capture.reference_frame = replace(original, pixels=bytes(64 * 64 * 3))
    with pytest.raises(ValueError, match="visual signal"):
        capture.object_crop(track, entity.id)
    assert repo.get(entity.id).reference_ids == [] and not service.key.path.exists()
    keys = []
    for value in ([20, 90, 40], [100, 150, 100]):
        capture.reference_frame = replace(original, pixels=bytes(value) * (64 * 64))
        jpeg, provenance = capture.object_crop(track, entity.id)
        key = service.store(
            entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(hours=1), confirmed=True
        )
        keys.append(key)
    capture.clear_media()
    listing = service.list(entity.id)
    assert {row["id"] for row in listing} == {str(key) for key in keys}
    assert all(row["quality"]["width"] == row["quality"]["height"] == 48 for row in listing)
    assert all(row["quality"]["warnings"] for row in listing)
    assert all(service.read(key).startswith(b"\xff\xd8") for key in keys)
    before_files = sorted(path.name for path in service.folder.glob("*.enc"))
    with pytest.raises(ValueError, match="different view"):
        service.store(
            entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(hours=1), confirmed=True
        )
    assert sorted(path.name for path in service.folder.glob("*.enc")) == before_files
    assert repo.get(entity.id).reference_ids == keys
    with Session(repo.engine) as session:
        stored = list(session.scalars(select(ReferenceRow)))
        assert len(stored) == 2 and all(row.payload["content_tag"] for row in stored)
        assert all("content_tag" not in row for row in listing)
    service.retire(keys[0], entity.name, confirmed=True)
    assert [row["id"] for row in service.list(entity.id)] == [str(keys[1])]
    assert repo.get(entity.id).reference_ids == [keys[1]]
    repo.close()
