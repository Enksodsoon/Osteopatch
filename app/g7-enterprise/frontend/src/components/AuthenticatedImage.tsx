import { useEffect, useState } from "react";
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
}: {
  path: string;
  alt: string;
  className?: string;
  label?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setUrl(null);
    setError(null);

    api.blobUrl(path)
      .then((u) => {
        objectUrl = u;
        if (cancelled) { URL.revokeObjectURL(u); return; }
        setUrl(u);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(String(e instanceof Error ? e.message : e));
      });

    return () => {
      cancelled = true;
      // Revoke on unmount and on every path change: a leaked object URL pins
      // the decoded bitmap in memory for the life of the tab.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  if (error) {
    return (
      <div className={`img-missing ${className ?? ""}`} role="status">
        <span className="img-missing-tag">no pixels</span>
        <span>
          {label ? `${label}: ` : ""}
          not available here ({error.split(":")[0]}). Nothing is shown rather than
          substituted.
        </span>
      </div>
    );
  }

  if (!url) {
    return <div className={`img-loading ${className ?? ""}`} aria-hidden="true" />;
  }

  return <img className={className} src={url} alt={alt} />;
}