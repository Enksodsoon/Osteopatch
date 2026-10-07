type IconName =
  | "review" | "images" | "reports" | "learn"
  | "zoom-in" | "zoom-out" | "fit" | "pan" | "annotate"
  | "eye" | "eye-off" | "fullscreen";

export function Icon({ name, size = 19 }: { name: IconName; size?: number }) {
  const drawing = {
    review: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    images: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="1.5" /><path d="m4 17 5-4 3 2 4-5 4 4" /></>,
    reports: <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path d="M15 3v5h5M9 12h7M9 16h7" /></>,
    learn: <><path d="M3 5.5c3.8-1.3 6.8-.8 9 1.5v13c-2.2-2.3-5.2-2.8-9-1.5z" /><path d="M21 5.5c-3.8-1.3-6.8-.8-9 1.5v13c2.2-2.3 5.2-2.8 9-1.5z" /></>,
    "zoom-in": <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5M10.5 7v7M7 10.5h7" /></>,
    "zoom-out": <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5M7 10.5h7" /></>,
    fit: <><path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5" /><path d="M8 8 3 3m13 5 5-5M8 16l-5 5m13-5 5 5" /></>,
    pan: <><path d="M12 2v20M2 12h20M12 2l-3 3m3-3 3 3M12 22l-3-3m3 3 3-3M2 12l3-3m-3 3 3 3m16-3-3-3m3 3-3 3" /></>,
    annotate: <><path d="m14 5 5 5M4 20l4.2-.9L20 7.3 16.7 4 4.9 15.8z" /><path d="M12 20h9" /></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    "eye-off": <><path d="m3 3 18 18M10.6 6.2A10 10 0 0 1 12 6c6 0 9.5 6 9.5 6a15 15 0 0 1-3 3.5M6.2 6.2C3.8 7.8 2.5 12 2.5 12s3.5 6 9.5 6c.6 0 1.2-.1 1.8-.2" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>,
    fullscreen: <><path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5" /></>,
  }[name];

  return <svg className="ui-icon" aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{drawing}</svg>;
}
