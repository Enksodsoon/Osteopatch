import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import * as api from "../api";

/**
 * An image from an authenticated endpoint.
 *
 * The PNGs on this surface sit behind `Authorization: Bearer`, which an
 * `<img src>` cannot send, so the bytes are fetched and shown as an object URL.
 *
 * The failure path is the point, not an afterthought: when pixels are absent or
 * the caller's project does not contain the image, this renders an explicit
 * notice. It never falls back to a placeholder gradient or a broken-image icon,
 * because "we could not load the image" and "here is a decorative placeholder"
 * must never look the same to someone judging a model's output.
 */
export function AuthenticatedImage({
  path,
  alt,
  className,
  label,
  style,
  onLoad,
  onUnavailable,
  testId,
}: {
  path: string;
  alt: string;
  className?: string;
  label?: string;
  style?: CSSProperties;
  onLoad?: () => void;
  onUnavailable?: () => void;
  testId?: string;
}) {
  const [loaded, setLoaded] = useState<{ path: string; url: string } | null>(null);
  const [failure, setFailure] = useState<{ path: string; error: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setLoaded(null);

    api.blobUrl(path)
      .then((u) => {
        objectUrl = u;
        if (cancelled) { URL.revokeObjectURL(u); return; }
        setLoaded({ path, url: u });
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setFailure({ path, error: String(e instanceof Error ? e.message : e) });
          onUnavailable?.();
        }
      });

    return () => {
      cancelled = true;
      // Revoke on unmount and on every path change: a leaked object URL pins
      // the decoded bitmap in memory for the life of the tab.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path, onUnavailable]);

  const current = loaded?.path === path ? loaded.url : null;
  const error = failure?.path === path ? failure.error : null;

  if (error) {
    return (
      <div className={`img-missing ${className ?? ""}`} role="status">
        <span className="img-missing-tag">no pixels</span>
        <span>
          {label ? `${label}: ` : ""}
          not available here. Nothing is shown in place of missing pixels.
        </span>
      </div>
    );
  }

  if (!current) {
    return <div className={`img-loading ${className ?? ""}`} aria-hidden="true" />;
  }

  return <img className={className} src={current} alt={alt} style={style} onLoad={onLoad}
    data-testid={testId}
    onError={() => {
      URL.revokeObjectURL(current);
      setLoaded(null);
      setFailure({ path, error: "image bytes could not be decoded" });
      onUnavailable?.();
    }} />;
}
