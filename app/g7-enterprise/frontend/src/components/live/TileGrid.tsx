import { useState } from "react";
import type { LiveMosaic, LiveTile } from "../../types";
import { CLASS_LABELS, CLASSES } from "../../types";

/**
 * One cell per tile, in the server's grid order.
 *
 * Rebuilt from the `tiles` array rather than the server's mosaic PNG for two
 * reasons: each cell can then carry its own uncertainty, and each is clickable.
 * A tile whose top two scores are indistinguishable is drawn hatched, not in a
 * class colour — the single most important honesty decision on this screen. A
 * confident-looking colour here would be the UI lying about the model.
 */
export function TileGrid({
  tiles,
  mosaic,
  onInspect,
}: {
  tiles: LiveTile[];
  mosaic: LiveMosaic;
  onInspect: (t: LiveTile) => void;
}) {
  const [sel, setSel] = useState<number | null>(null);

  // An indeterminate tile STILL has a predicted_class — the model returned one,
  // it just is not separated enough to trust. Counting it in the class tally AND
  // again as "indeterminate" would read as more tiles than exist, so the
  // indeterminate count is labelled as a subset of the tally.
  const tally = CLASSES.map((c) => ({
    cls: c,
    n: tiles.filter((t) => t.predicted_class === c).length,
  }));
  const undecidable = tiles.filter((t) => t.confidence === "indeterminate").length;
  const undecoded = tiles.filter((t) => t.decode_error).length;

  return (
    <div className="grid-wrap">
      <div className="tally">
        {tally.map((t) => (
          <span className={`tally-chip cl-${t.cls}`} key={t.cls}>
            <b>{t.n}</b> {t.cls}
          </span>
        ))}
        {undecidable > 0 && (
          <span className="tally-chip tally-uncertain">
            <b>{undecidable}</b> indeterminate
            <span className="tally-note">of those {tiles.length} — no class trusted</span>
          </span>
        )}
        {undecoded > 0 && (
          <span className="tally-chip tally-undecoded">
            <b>{undecoded}</b> undecoded
          </span>
        )}
      </div>

      <div
        className="tile-grid"
        style={{ gridTemplateColumns: `repeat(${mosaic.cols}, var(--cell))` }}
        role="grid"
        aria-label={`${tiles.length} scored tiles in a ${mosaic.cols} by ${mosaic.rows} grid`}
      >
        {tiles.map((t) => {
          const cls = t.predicted_class ?? "";
          const state = t.decode_error ? "undecoded"
            : t.confidence === "indeterminate" ? "uncertain"
            : cls ? `cl-${cls}` : "unknown";
          // `cl-*` carries the colour as a custom property; the rest style the
          // "we are not asserting a class" states.
          const isSel = sel === t.tile_index;
          return (
            <button
              type="button"
              key={t.tile_index}
              role="gridcell"
              aria-label={
                t.decode_error ? `Tile ${t.tile_index}, could not be decoded`
                : t.confidence === "indeterminate"
                  ? `Tile ${t.tile_index}, indeterminate, no class asserted`
                : `Tile ${t.tile_index}, ${cls}`
              }
              aria-selected={isSel}
              className={`tile ${state}${isSel ? " sel" : ""}`}
              onClick={() => { setSel(t.tile_index); onInspect(t); }}
            />
          );
        })}
      </div>

      <ul className="legend">
        {CLASSES.map((c) => (
          <li key={c}><i className={`sw cl-${c}`} /> {CLASS_LABELS[c]}</li>
        ))}
        <li><i className="sw uncertain" /> Indeterminate — no class asserted</li>
        {undecoded > 0 && <li><i className="sw undecoded" /> Could not be decoded</li>}
      </ul>
    </div>
  );
}

/**
 * Where a human should look first, ranked by how little the top two classes
 * were separated.
 *
 * Computed from the tiles rather than taken from the upload response, so it is
 * present when a STORED run is reopened too — not only in the moment right
 * after an import. A reader-only persona (student, auditor) can only ever see
 * the reopened view, so deriving it here is what makes the guidance reachable
 * to them at all.
 */
export function UncertainRank({ tiles, limit = 5 }: { tiles: LiveTile[]; limit?: number }) {
  const ranked = [...tiles]
    .filter((t) => t.top_two_margin !== null)
    .sort((a, b) => (a.top_two_margin ?? 0) - (b.top_two_margin ?? 0))
    .slice(0, limit);
  if (ranked.length === 0) return null;
  return (
    <div className="uncertain">
      <h4>Most uncertain tiles — where a human should look first</h4>
      <ol>
        {ranked.map((t) => (
          <li key={t.tile_index}>
            <span className="mono subtle">#{t.tile_index}</span>
            <span>
              {t.confidence === "indeterminate" ? <b>indeterminate</b> : t.predicted_class ?? "—"}
            </span>
            <span className="muted small">
              separation {t.top_two_margin?.toFixed(3) ?? "n/a"}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Detail for one clicked tile. Also refuses to name a class when unclear. */
export function TileInspector({ tile }: { tile: LiveTile | null }) {
  if (!tile) {
    return (
      <p className="muted small tile-inspect-empty">
        Select any cell to see its scores. Hatched cells did not get a class.
      </p>
    );
  }
  if (tile.decode_error) {
    return (
      <div className="tile-inspect">
        <h4>Tile {tile.tile_index}</h4>
        <p className="err">Could not be decoded: {tile.decode_error}</p>
      </div>
    );
  }
  const undecided = tile.confidence === "indeterminate" || !tile.predicted_class;
  return (
    <div className="tile-inspect">
      <h4>
        Tile {tile.tile_index}
        <span className="mono subtle"> at {tile.x}, {tile.y}</span>
      </h4>
      {undecided ? (
        <p className="conf conf-indeterminate">
          <b>Indeterminate</b> — top two separation{" "}
          {tile.top_two_margin?.toFixed(3) ?? "n/a"}. No class is asserted for this tile.
        </p>
      ) : (
        <p className={`conf conf-${tile.confidence}`}>
          <b>{tile.predicted_class}</b> · {CLASS_LABELS[tile.predicted_class!]}
          {tile.top_two_margin !== null && (
            <> · separation {tile.top_two_margin.toFixed(3)}</>
          )}
        </p>
      )}
      {tile.scores && (
        <ul className="mini-scores">
          {CLASSES.map((c) => (
            <li key={c}>
              <span>{c}</span>
              <span className="mono">{tile.scores![c].toFixed(4)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">Class scores, uncalibrated — not probabilities.</p>
    </div>
  );
}