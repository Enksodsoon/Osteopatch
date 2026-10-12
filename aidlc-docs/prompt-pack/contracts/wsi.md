# Shared contract: wsi

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Only enable the spatial WSI workflow for a real whole-slide file with verified slide identity, readable pyramids, and a tile-coordinate manifest. A patch collection without these prerequisites remains patch-only. A contact sheet is an explicitly labeled gallery, never a reconstructed original slide.

All persisted annotation and tile geometry uses level-0 image pixels, origin top-left, x rightward, y downward. TileRecord: tile_id, slide_id, source_sha256, x0, y0, width0, height0, read_level, downsample, output_width, output_height, tissue_fraction nullable, prediction_id nullable, preprocessing_hash. Browser CSS pixels and OpenSeadragon viewport coordinates are not persisted as image coordinates. Verify round-trip transforms at multiple zooms, rotations, and nonzero offsets.

MPP and objective power are metadata, not guessed. A scale bar uses mpp_x/mpp_y only when both are valid; otherwise show pixel scale or unavailable. Preserve aspect ratio and explicitly record resampling. Vendor support is capability-based; do not claim VSI or arbitrary OME-TIFF support from extension matching or from OpenSlide installation alone. Conversion is a separate provenance-bearing, approved adapter.

An AI slide map places actual tile predictions in their footprints and leaves missing/unprocessed areas transparent. Never interpolate a smooth tumor segmentation from sparse patch labels. Aggregation over a complete, non-overlapping, adequately QC'd tile mask may be labeled classified analyzed-tile area with a denominator and uncovered area; not clinical necrosis %, response, grade, or prognosis. Sparse or overlapping sampling receives count summaries only.

Inference/conversion run in bounded local worker processes, not inside every tile HTTP request. Authz applies to manifests and every tile URL. Cache keys include asset hash, scope, transform, and tile coordinates. Do not decode a gigapixel slide into one full RGB array.
