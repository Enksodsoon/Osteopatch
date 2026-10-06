import type { LiveRun } from "../../types";

/**
 * What actually happened, in the words the server used.
 *
 * Every field here is nullable because the file genuinely may not carry it.
 * `null` is rendered as an explicit "not in file" — never as 0, never blank,
 * and never estimated. This strip is the difference between "the system knows"
 * and "the system guessed".
 */
export function ProvenanceStrip({ run }: { run: LiveRun }) {
  const fact = (label: string, value: string | number | null | undefined, unit?: string) => (
    <div className="fact" key={label}>
      <dt>{label}</dt>
      <dd className={value === null || value === undefined || value === "" ? "absent" : undefined}>
        {value === null || value === undefined || value === ""
          ? "not in file"
          : `${value}${unit ? ` ${unit}` : ""}`}
      </dd>
    </div>
  );

  return (
    <dl className="provenance">
      {fact("engine", run.engine)}
      {fact("levels read", run.level_count)}
      {fact("mpp", run.mpp_x !== null && run.mpp_y !== null ? `${run.mpp_x} × ${run.mpp_y}` : null)}
      {fact("objective", run.objective_power)}
      {fact("vendor", run.vendor)}
      {fact("dimensions", run.width && run.height ? `${run.width} × ${run.height}` : null, "px")}
      {fact("tiles scored", `${run.tile_count} of ${run.tiles_available}`)}
      {fact("elapsed", run.latency_ms !== null ? (run.latency_ms / 1000).toFixed(2) : null, "s")}
      <div className="fact wide">
        <dt>model</dt>
        <dd className="mono">{run.model_id}</dd>
      </div>
      <div className="fact wide">
        <dt>bundle sha256</dt>
        <dd className="mono">{run.model_bundle_sha256}</dd>
      </div>
    </dl>
  );
}