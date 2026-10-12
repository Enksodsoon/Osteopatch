import { useEffect, useRef } from "react";
import { Text } from "@antv/t8";
import narrativeText from "./g4-evidence.t8.md?raw";

// Source example only: @antv/t8 is not installed in OsteoPatch app dependencies.
export function G4EvidenceNarrative() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!host.current) return;
    const view = new Text(host.current);
    view.theme("light").render(narrativeText);
    return () => view.unmount();
  }, []);

  return (
    <section aria-label="Frozen G4 evaluation narrative">
      <div ref={host} />
    </section>
  );
}
