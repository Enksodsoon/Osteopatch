"""Whole-slide image reading.

Capability-detected, never assumed. OpenSlide is used when present; otherwise a
pure-Python Pillow reader handles plain tiled/striped TIFF.

Design rule that must not be relaxed: **absent metadata is reported as null,
never inferred.** A file with no micron-per-pixel tag yields ``mpp_x = None``.
The reader does not estimate, default, or fabricate a physical scale.

No custom WSI binary parser exists or will be written; OpenSlide covers the
vendor formats.

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""