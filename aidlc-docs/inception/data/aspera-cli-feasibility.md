# Aspera CLI feasibility — U1 (investigation only, NO transfer executed)

**Status:** desk analysis from documented facts (TCIA_Aspera_CLI_Downloads notebook + `aspera-cli` docs). **Nothing installed, nothing transferred.** No Ruby/ascli on this Windows control plane. This collection = TCIA Faspex **package id 752**.

## Client + prerequisites
- **Ruby ≥ 3.1** (the `aspera-cli` gem's documented minimum).
- `gem install aspera-cli` (Apache-2.0) → provides the `ascli` command.
- `ascli conf ascp install` — downloads the IBM Aspera `ascp` transfer binary (the gem ships the CLI, not the proprietary transfer engine; this step fetches it).
- Platform: **Linux** per the documented notebook. Not supported out-of-the-box on this Windows host without Ruby + ascp; and Windows is **not** the intended place for the image data anyway (cloud-first intent).

## Authentication required?
- **Expected: NO.** The documented pattern is `ascli faspex5 packages receive --url='<public faspex package URL>'`. The public package URL carries its own passcode, so no TCIA account/login is needed for a public package. (To be confirmed empirically only when a transfer is actually run, which U1 does not do.)

## Can a public package be addressed by URL directly?
- **Expected: YES.** `--url='<public pkg URL>'` is exactly the documented addressing mode for a public Faspex 5 package; package id 752 is the identifier for this collection.

## Can a Linux AWS env run it → ephemeral disk → S3?
- **Yes, by design.** `ascli` + `ascp` run headlessly on a Linux instance/container with no GUI. Flow: Linux ephemeral compute → `ascli faspex5 packages receive` into local ephemeral disk → `aws s3 cp/sync` into project `raw/` → terminate compute (nothing persists locally). This is the realistic supported ingest once AWS access (B2) is unblocked. The one Aspera fetch may transit a machine but is not persistently stored locally — consistent with owner intent.

## Expected temporary storage vs caps
- Published image payload ≈ **196.84 MB** (JPG). Allow headroom for the transfer + any transient conversion ⇒ estimate **~200 MB**, well under the **500 MB** source cap and the **2 GB** total U1 footprint cap. The PathDB objects are `.tiff` tiles; if the Aspera package delivers `.tiff` the payload could be larger than the JPG figure — **confirm actual size via `ascli … browse` before any receive** (see next point). Abort + report if either cap would be exceeded.

## Does `ascli browse` list sizes before transfer?
- **Yes.** `aspera-cli` supports `browse` to **list files and their sizes before any receive**, and selective file/dir receive. This is the pre-flight size check that satisfies the "inspect expected size before download" bound — run it first, compare to caps, and only then decide.

## Verdict
**FEASIBLE on a Linux AWS compute step, not on this Windows control plane.** No auth expected; public package addressable by URL (pkg 752); `browse` gives sizes pre-transfer; estimated temp storage ~200 MB (verify via `browse`) within caps. **Blocked today by B2 (no AWS access configured on this host).** Do NOT start the receive. PathDB plain-HTTP object GET is an alternative image route that needs no Aspera/Ruby at all (one object already probed OK) and may be simpler for a bounded, per-row fetch.
