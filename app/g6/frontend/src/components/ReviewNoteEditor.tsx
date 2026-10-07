import { useState } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function ReviewNoteEditor({ value, onChange, placeholder }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="review-note-editor">
      <textarea
        id="review-note"
        className="review-note-input"
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={placeholder}
        rows={expanded ? 10 : 4}
        data-testid="review-note"
        aria-label={placeholder}
      />
      <button
        type="button"
        className="review-note-expand"
        onClick={() => setExpanded((current) => !current)}
        aria-label={expanded ? "Collapse note editor" : "Expand note editor"}
        data-testid="review-note-expand"
      >
        {expanded ? "Collapse" : "Expand"}
      </button>
    </div>
  );
}
