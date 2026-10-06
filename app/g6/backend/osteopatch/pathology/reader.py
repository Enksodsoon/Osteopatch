"""Whole-slide image readers: OpenSlide first, Pillow fallback.

Two engines behind one protocol:

  * ``OpenSlideReader``  — preferred. Handles the vendor WSI formats and gives
    real pyramid levels, downsample factors, MPP and vendor properties.
  * ``PillowTiffReader`` — pure-Python fallback for tiled/striped TIFF. Reads
    dimensions and whatever physical-scale tags the file actually carries.

THE CONTRACT THAT MATTERS: every field that a file does not genuinely contain
is returned as ``None``. MPP, objective power and vendor are **never**
estimated, defaulted, or inferred. A reader that reports a plausible number it
made up is worse than one that reports nothing, because downstream code cannot
tell the difference.

Engines are detected at runtime via :func:`engine_report`, which the API
exposes so a deployment can state which backend it is actually using.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SlideProperties:
    """Whole-slide metadata. ``None`` means "not present in this file"."""

    width: int
    height: int
    level_count: int
    level_dimensions: list[tuple[int, int]]
    level_downsamples: list[float]
    format: str | None = None
    mpp_x: float | None = None
    mpp_y: float | None = None
    objective_power: float | None = None
    vendor: str | None = None
    engine: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


class ReaderUnavailable(RuntimeError):
    """Raised when a requested engine is not installed. Never a silent fallback."""


class SlideReadError(RuntimeError):
    """Raised when a file cannot be read as a slide at all."""


@runtime_checkable
class SlideReader(Protocol):
    """Minimal read surface needed by ingestion."""

    engine: str

    def properties(self) -> SlideProperties: ...

    def read_region(self, x: int, y: int, level: int, width: int, height: int):
        """Return a PIL image for a level-``level`` region."""

    def close(self) -> None:
        """Release the underlying handle. Idempotent.

        Both engines own something that must be released (an openslide handle,
        an open PIL file), so every caller that opens a slide closes it. Declared
        here so a caller holding only a ``SlideReader`` can do so without a cast.
        """


# ---------------------------------------------------------------------------
# Optional OpenSlide engine
# ---------------------------------------------------------------------------

_OPENSLIDE_VERSION: str | None = None
_OPENSLIDE_LIB_VERSION: str | None = None


def _probe_openslide():
    """Import openslide, or return None. Never raises."""
    global _OPENSLIDE_VERSION, _OPENSLIDE_LIB_VERSION
    try:
        import openslide
    except Exception:
        return None
    if _OPENSLIDE_VERSION is None:
        _OPENSLIDE_VERSION = getattr(openslide, "__version__", "unknown")
        _OPENSLIDE_LIB_VERSION = getattr(openslide, "__library_version__", "unknown")
    return openslide


class OpenSlideReader:
    """Preferred engine. Requires ``openslide-python`` + the native library."""

    engine = "openslide"

    def __init__(self, path: str | Path):
        self._mod = _probe_openslide()
        if self._mod is None:
            raise ReaderUnavailable(
                "openslide-python is not importable (native OpenSlide library "
                "missing). Install the `wsi` extra, or use the Pillow fallback."
            )
        self.path = Path(path)
        try:
            self._slide = self._mod.OpenSlide(str(self.path))
        except Exception as exc:  # pragma: no cover - depends on input file
            raise SlideReadError(f"OpenSlide could not open {self.path.name}: {exc}") from exc

    def properties(self) -> SlideProperties:
        s = self._slide
        # Properties keys are vendor-specific; absent keys yield None.
        raw = dict(s.properties)

        def num(*keys: str) -> float | None:
            for k in keys:
                v = raw.get(k)
                if v is None:
                    continue
                m = re.search(r"-?\d+(?:\.\d+)?", str(v))
                if m:
                    try:
                        return float(m.group())
                    except ValueError:
                        continue
            return None

        return SlideProperties(
            width=int(s.dimensions[0]),
            height=int(s.dimensions[1]),
            level_count=int(s.level_count),
            level_dimensions=[
                (int(s.level_dimensions[i][0]), int(s.level_dimensions[i][1]))
                for i in range(s.level_count)
            ],
            level_downsamples=[float(s.level_downsamples[i]) for i in range(s.level_count)],
            format=raw.get("openslide.vendor") or raw.get("aperio.AppMag"),
            mpp_x=num("openslide.mpp-x", "aperio.MPP"),
            mpp_y=num("openslide.mpp-y", "aperio.MPP"),
            objective_power=num("openslide.objective-power", "aperio.AppMag"),
            vendor=raw.get("openslide.vendor"),
            engine=self.engine,
        )

    def read_region(self, x: int, y: int, level: int, width: int, height: int):
        return self._slide.read_region((x, y), level, (width, height))

    def close(self) -> None:
        try:
            self._slide.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pure-Python fallback
# ---------------------------------------------------------------------------


class PillowTiffReader:
    """Fallback for plain tiled/striped TIFF.

    Reports only what Pillow genuinely exposes. A TIFF without physical-scale
    tags returns ``mpp_x = None`` rather than a guess — TIFF resolution tags
    describe *printing* intent, not microscopy calibration, and treating them as
    micron-per-pixel would be an invention.
    """

    engine = "pillow"

    def __init__(self, path: str | Path):
        from PIL import Image  # lazy: keeps import cost off the hot path

        self.path = Path(path)
        self._Image = Image
        try:
            self._img = Image.open(self.path)
            self._img.load()
        except Exception as exc:
            raise SlideReadError(f"Pillow could not open {self.path.name}: {exc}") from exc

    def properties(self) -> SlideProperties:
        width, height = self._img.size
        fmt = (self._img.format or "").lower() or None
        return SlideProperties(
            width=width,
            height=height,
            # Pillow exposes no pyramid for a flat TIFF.
            level_count=1,
            level_dimensions=[(width, height)],
            level_downsamples=[1.0],
            format=fmt,
            # NOT derived from TIFF resolution tags: those are print intent,
            # not a microscopy calibration. Absent => None.
            mpp_x=None,
            mpp_y=None,
            objective_power=None,
            vendor=None,
            engine=self.engine,
        )

    def read_region(self, x: int, y: int, level: int, width: int, height: int):
        if level not in (0,):
            raise SlideReadError(
                f"the Pillow fallback reports a single level; level {level} requested"
            )
        return self._img.crop((x, y, x + width, y + height))

    def close(self) -> None:
        try:
            self._img.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

#: Preferred engine order. OpenSlide first; Pillow is always available.
ENGINE_PREFERENCE = ("openslide", "pillow")


def open_slide(path: str | Path, *, engine: str | None = None) -> SlideReader:
    """Open ``path`` with the best available engine.

    ``engine`` forces a specific one and raises rather than falling back, so a
    caller that genuinely requires OpenSlide never silently gets a weaker one.

    Without an explicit engine, TWO different failures are handled differently:

    * ``ReaderUnavailable`` — OpenSlide is not installed at all. Fall back to
      Pillow, which is always present.
    * ``SlideReadError``    — OpenSlide IS installed but cannot read THIS
      file. That is a per-file outcome, not a missing capability: a generic
      TIFF or a PNG, neither of which carries a vendor SVS/NDPI tag set, hits
      it. Fall back too.

    The second case used to propagate, so ``open_slide`` raised on every file
    OpenSlide did not recognise while its own docstring promised a Pillow
    fallback — which meant a PNG upload crashed instead of opening.

    A fallback that ALSO fails still raises, naming both engines so the cause
    is not reduced to whichever was tried first.
    """
    if engine:
        if engine == "openslide":
            return OpenSlideReader(path)
        if engine == "pillow":
            return PillowTiffReader(path)
        raise ReaderUnavailable(f"unknown engine: {engine!r}")

    try:
        return OpenSlideReader(path)
    except ReaderUnavailable:
        return PillowTiffReader(path)
    except SlideReadError as openslide_error:
        try:
            return PillowTiffReader(path)
        except SlideReadError as pillow_error:
            raise SlideReadError(
                f"no engine could read {Path(path).name}: "
                f"openslide -> {openslide_error}; pillow -> {pillow_error}"
            ) from pillow_error


def available_engines() -> list[str]:
    out: list[str] = []
    if _probe_openslide() is not None:
        out.append("openslide")
    out.append("pillow")
    return out


def engine_report() -> dict:
    """Capability snapshot, surfaced on /health and by scripts/check_wsi_engines.py."""
    mod = _probe_openslide()
    return {
        "available": available_engines(),
        "preference": list(ENGINE_PREFERENCE),
        "openslide": {
            "available": mod is not None,
            "binding_version": _OPENSLIDE_VERSION if mod else None,
            "library_version": _OPENSLIDE_LIB_VERSION if mod else None,
        },
        "fallback_note": (
            "The Pillow fallback reports only genuinely present metadata. "
            "mpp / objective_power / vendor are null when the file does not "
            "carry them — they are never estimated. open_slide() falls back to "
            "Pillow both when OpenSlide is absent AND when OpenSlide is present "
            "but cannot read this particular file (a generic TIFF or PNG, "
            "which carry no vendor tag set)."
        ),
    }


__all__ = [
    "SlideProperties",
    "SlideReader",
    "ReaderUnavailable",
    "SlideReadError",
    "OpenSlideReader",
    "PillowTiffReader",
    "open_slide",
    "available_engines",
    "engine_report",
    "ENGINE_PREFERENCE",
]