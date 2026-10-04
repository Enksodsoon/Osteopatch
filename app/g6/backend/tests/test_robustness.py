"""Robustness tests for independently-hardened paths: image serving decode
failures / path safety, and list_images pagination clamping.

These exercise defensive guards added without changing behavior for valid
inputs. Torch-free (web venv).
"""
from __future__ import annotations

import pytest

from osteopatch import config, images, queries


# ---------------------------------------------------------------------------
# Image serving: not-found and corrupt-decode all fail CLEANLY.
# ---------------------------------------------------------------------------
def test_thumbnail_unknown_image_raises_not_found(conn):
    with pytest.raises(images.ImageNotFound):
        images.thumbnail_png(conn, "does-not-exist")


def test_corrupt_tiff_raises_decode_error(conn, tmp_path, monkeypatch):
    # Point TIFFS_DIR + THUMBS_DIR at a temp dir and drop a bogus "tiff" that
    # PIL cannot decode. The seed fixture already inserted source_qc rows whose
    # tiff_filename is "<image_id>.tiff".
    tiffs = tmp_path / "tiffs"
    thumbs = tmp_path / "thumbs"
    tiffs.mkdir()
    thumbs.mkdir()
    (tiffs / "img-clear-nt.tiff").write_bytes(b"not a real tiff, just bytes")
    monkeypatch.setattr(config, "TIFFS_DIR", tiffs)
    monkeypatch.setattr(config, "THUMBS_DIR", thumbs)

    with pytest.raises(images.ImageDecodeError):
        images.thumbnail_png(conn, "img-clear-nt")
    with pytest.raises(images.ImageDecodeError):
        images.full_png(conn, "img-clear-nt")


def test_corrupt_tiff_maps_to_422_over_http(client, conn, tmp_path, monkeypatch):
    tiffs = tmp_path / "tiffs"
    thumbs = tmp_path / "thumbs"
    tiffs.mkdir()
    thumbs.mkdir()
    (tiffs / "img-clear-nt.tiff").write_bytes(b"corrupt")
    monkeypatch.setattr(config, "TIFFS_DIR", tiffs)
    monkeypatch.setattr(config, "THUMBS_DIR", thumbs)

    r = client.get("/v1/images/img-clear-nt/thumbnail")
    assert r.status_code == 422
    assert r.json()["error"] == "image could not be decoded"


def test_unknown_thumbnail_maps_to_404_over_http(client):
    r = client.get("/v1/images/ghost/thumbnail")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Pagination clamping: direct callers can't produce a bad slice.
# ---------------------------------------------------------------------------
def test_list_images_clamps_nonpositive_page(conn):
    out = queries.list_images(conn, page=0, page_size=50)
    assert out["page"] == 1


def test_list_images_clamps_nonpositive_page_size(conn):
    out = queries.list_images(conn, page=1, page_size=0)
    assert out["page_size"] == 1
    assert len(out["items"]) == 1  # exactly one item on a size-1 page


def test_list_images_clamps_oversize_page_size(conn):
    out = queries.list_images(conn, page=1, page_size=10_000)
    assert out["page_size"] == 500


def test_list_images_negative_page_does_not_wrap_slice(conn):
    # a negative page previously could yield a negative slice start; clamped to 1.
    out = queries.list_images(conn, page=-5, page_size=2)
    assert out["page"] == 1
    assert len(out["items"]) <= 2
