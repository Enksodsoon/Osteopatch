#!/usr/bin/env python
"""Build a repeatable demo whole-slide image from real corpus patches.

WHY
---
There is no ``.svs``/``.ndpi`` in this repository, and pixel data is
gitignored by design. So the "import a WSI" demo needs a slide it can always
rebuild from what IS here: the 1,144 verified H&E patches under
``runtime-artifacts/images``.

The result is a genuine tiled TIFF mosaic of real tissue with real pyramid
levels, plus a manifest mapping every tile coordinate back to the corpus
``image_id`` and that image's FROZEN prediction. That lets a presenter point at
a mosaic cell and say "this cell is corpus patch X, and the frozen model called
it Y" — which is the honest way to demo a second, different model.

THE HONESTY RULE
----------------
After writing, this script re-opens the file through the SAME reader the
application uses and prints what that reader ACTUALLY reports: level count,
per-level dimensions, format, engine, mpp. It does not assert a pyramid it did
not verify.

A multi-page TIFF written by Pillow is often read by OpenSlide's generic-TIFF
driver as a single level, because OpenSlide's format detection keys on vendor
tags this file does not carry. If that happens the script says so plainly and
exits non-zero under ``--require-pyramid``. A demo slide that is honestly
single-level is a valid artefact; a demo slide that claims a pyramid it does not
have is not.

    python scripts/make_demo_slide.py
    python scripts/make_demo_slide.py --cols 12 --rows 10 --require-pyramid
    python scripts/make_demo_slide.py --out custom/path.tif --json
    python scripts/make_demo_slide.py --report docs/evidence/demo-slide.json

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "app" / "g6" / "backend"))

from osteopatch import config, db  # noqa: E402
from osteopatch.pathology import reader  # noqa: E402

DEFAULT_OUT = config.RUNTIME_ARTIFACTS_ROOT / "demo-slides" / "osteopatch-demo-slide.tif"
MANIFEST_SUFFIX = ".manifest.json"


def choose_patches(conn, count: int) -> list[dict]:
    """Pick ``count`` corpus images, richest-information first.

    Deterministic: the frozen review-priority order is a pure function of the
    scores, so the same read model always yields the same demo slide. Classes
    are interleaved by walking the priority order and round-robining the three
    canonical classes, so the mosaic shows a spread rather than 120 cells of one
    colour.
    """
    from osteopatch import queries  # type: ignore

    listing = queries.list_images(
        conn, sort="priority", filt="all", q=None, page=1, page_size=500, project_id=None
    )
    by_class: dict[str, list[dict]] = {c: [] for c in config.CANONICAL_CLASSES}
    for item in listing["items"]:
        pred = item.get("prediction")
        if pred:
            by_class[pred["predicted_class"]].append(item)

    out: list[dict] = []
    i = 0
    while len(out) < count:
        progressed = False
        for cls in config.CANONICAL_CLASSES:
            if i < len(by_class[cls]) and len(out) < count:
                out.append(by_class[cls][i])
                progressed = True
        if not progressed:
            break
        i += 1
    return out


def build(path: Path, cols: int, rows: int, tile_px: int) -> list[dict]:
    """Write a tiled TIFF with reduced-resolution pages. Returns the manifest."""
    from PIL import Image

    if not config.TIFFS_DIR.is_dir():
        raise SystemExit(f"corpus pixels missing: {config.TIFFS_DIR}\nrun scripts/prepare_runtime.py")

    conn = db.connect()
    db.run_migrations(conn)
    needed = cols * rows
    patches = choose_patches(conn, needed)
    if len(patches) < needed:
        raise SystemExit(
            f"need {needed} scored corpus patches, only {len(patches)} available"
        )

    width, height = cols * tile_px, rows * tile_px
    base = Image.new("RGB", (width, height), (255, 255, 255))
    manifest: list[dict] = []
    missing: list[str] = []

    for i, item in enumerate(patches):
        tiff = config.TIFFS_DIR / f"{item['image_id']}.tiff"
        if not tiff.exists():
            missing.append(item["image_id"])
            continue
        col, row = i % cols, i // cols
        with Image.open(tiff) as im:
            tile = im.convert("RGB").resize((tile_px, tile_px), Image.LANCZOS)
        base.paste(tile, (col * tile_px, row * tile_px))
        pred = item["prediction"]
        manifest.append({
            "tile_index": i, "col": col, "row": row,
            "x": col * tile_px, "y": row * tile_px, "size": tile_px,
            "image_id": item["image_id"],
            "source_group": item["source_group"],
            "frozen_model_version": pred["model_version"],
            "frozen_model_bundle_sha256": pred["model_bundle_hash"],
            "frozen_predicted_class": pred["predicted_class"],
            "frozen_top_two_margin": pred["top_two_margin"],
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    # Reduced-resolution pages: OpenSlide's generic-TIFF driver looks for these.
    level1 = base.resize((width // 4, height // 4), Image.LANCZOS)
    level2 = base.resize((width // 16, height // 16), Image.LANCZOS)
    base.save(
        path, format="TIFF", save_all=True,
        append_images=[level1, level2], compression="tiff_lzw",
    )

    manifest_doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": (
            "Demo slide assembled from real corpus patches. Tile -> image_id so a "
            "presenter can compare a live run against the frozen prediction."
        ),
        "slide": {
            "path": path.name, "cols": cols, "rows": rows, "tile_px": tile_px,
            "width": width, "height": height,
            "tiles": len(manifest), "tiles_missing_pixels": missing,
            "assembled_from": "runtime-artifacts/images (gitignored runtime data)",
        },
        "canonical_classes": list(config.CANONICAL_CLASSES),
        "disclaimer": config.DISCLAIMER,
        "tiles": manifest,
    }
    manifest_path = path.with_suffix(MANIFEST_SUFFIX)
    manifest_path.write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")
    # stderr, not stdout: `--json` promises stdout is the report ALONE.
    print(f"manifest -> {manifest_path}", file=sys.stderr)
    return manifest


def verify(path: Path) -> dict:
    """Re-open through the application's own reader and report what it SAYS.

    This is the part that matters: the report is whatever ``reader`` returns,
    not whatever the writer intended.
    """
    report: dict = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return report
    report["bytes"] = path.stat().st_size

    try:
        slide = reader.open_slide(path)
    except Exception as exc:
        report["readable"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report

    try:
        props = slide.properties().to_dict()
    except Exception as exc:
        report["readable"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    finally:
        slide.close()

    report.update({
        "readable": True,
        "engine": props["engine"],
        "format": props["format"],
        "width": props["width"],
        "height": props["height"],
        "level_count": props["level_count"],
        "level_dimensions": [list(d) for d in props["level_dimensions"]],
        "level_downsamples": props["level_downsamples"],
        "mpp_x": props["mpp_x"],
        "mpp_y": props["mpp_y"],
        "objective_power": props["objective_power"],
        "vendor": props["vendor"],
    })
    report["is_pyramid"] = props["level_count"] > 1
    report["honest_note"] = (
        "OpenSlide reports a multi-level pyramid."
        if report["is_pyramid"]
        else (
            "The reader reports a SINGLE level. This file has no vendor SVS/NDPI "
            "tags and no OME-XML, so OpenSlide's format detection reads it as a "
            "flat generic TIFF even though extra reduced-resolution pages were "
            "written. The slide is still valid input and tiles fine; it is "
            "simply not a pyramid as far as any reader can see."
        )
    )
    return report


def _relative_to_repo(path: Path) -> str:
    """Repo-relative POSIX path, or the absolute path if it lives elsewhere.

    Evidence records name a file by a path that still resolves from the repo
    root, so a reader can find the artefact the record describes.
    """
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--cols", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--tile-px", type=int, default=config.LIVE_TILE_PX)
    ap.add_argument("--require-pyramid", action="store_true",
                    help="exit 1 unless the reader confirms >1 level")
    ap.add_argument("--json", action="store_true", help="print only the verify report as JSON")
    ap.add_argument("--report", type=Path, default=None, metavar="PATH",
                    help="write the verification record (report + slide sha256 + why it "
                         "matters) to PATH as JSON; independent of --json")
    args = ap.parse_args()

    if args.cols < 1 or args.rows < 1:
        raise SystemExit("--cols and --rows must be >= 1")

    if not args.json:
        print(f"Building demo slide: {args.cols}x{args.rows} tiles of {args.tile_px}px "
              f"-> {args.out}", file=sys.stderr)
    t0 = time.time()
    build(args.out, args.cols, args.rows, args.tile_px)
    report = verify(args.out)
    report["build_seconds"] = round(time.time() - t0, 2)
    report["engines_available"] = reader.available_engines()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n--- what the reader ACTUALLY reports ---")
        if not report.get("readable"):
            print(f"  UNREADABLE: {report.get('error')}")
        else:
            print(f"  engine            : {report['engine']}")
            print(f"  format            : {report['format']}")
            print(f"  dimensions        : {report['width']} x {report['height']}")
            print(f"  level_count       : {report['level_count']}")
            for i, dim in enumerate(report["level_dimensions"]):
                ds = report["level_downsamples"][i] if i < len(report["level_downsamples"]) else "?"
                print(f"    level {i}: {dim[0]} x {dim[1]}  (downsample {ds})")
            print(f"  mpp_x / mpp_y     : {report['mpp_x']} / {report['mpp_y']}"
                  f"   <- null means the file carries none; never estimated")
            print(f"  objective_power   : {report['objective_power']}")
            print(f"  vendor            : {report['vendor']}")
            print(f"  file size         : {report['bytes'] / 1e6:.1f} MB")
        print(f"\n  VERDICT: {report.get('honest_note', 'unreadable')}")
        print(f"  built in {report['build_seconds']}s")

    if args.report:
        # The evidence record is the SAME report, plus what a reader of the file
        # later needs to know it was actually produced this way. Nothing here
        # upgrades the verdict: is_pyramid stays whatever the reader said.
        slide = args.out
        doc = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": "scripts/make_demo_slide.py" + (
                f" --cols {args.cols} --rows {args.rows} --tile-px {args.tile_px}"),
            "purpose": (
                "What the slide reader ACTUALLY reports for the demo WSI. This record does "
                "not assert a pyramid: level_count is recorded exactly as read."),
            "slide_path_relative": _relative_to_repo(slide),
            "slide_sha256": _sha256_file(slide),
            "manifest_path_relative": _relative_to_repo(
                slide.with_name(slide.stem + MANIFEST_SUFFIX)),
            "report": report,
            "conclusion": (
                "level_count=%s, level_dimensions=%s, mpp=%s/%s, vendor=%s, "
                "is_pyramid=%s. The reader is authoritative here. %s"
                % (report.get("level_count"), report.get("level_dimensions"),
                   report.get("mpp_x"), report.get("mpp_y"), report.get("vendor"),
                   report.get("is_pyramid"), report.get("honest_note", "unreadable"))),
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.report}", file=sys.stderr)

    if args.require_pyramid and not report.get("is_pyramid"):
        print("FAIL: --require-pyramid was set but the reader reports level_count == 1",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
