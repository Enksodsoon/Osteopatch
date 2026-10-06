import { useRef, useEffect, useState } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function ReviewNoteEditor({ value, onChange, placeholder }: Props) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (buttonRef.current) {
      const style = window.getComputedStyle(buttonRef.current);
      const width = parseFloat(style.width) / parseFloat(style.fontSize) * parseFloat(style.fontSize);
      buttonRef.current.style.width = `${width}ch`;
    }
  }, []);

  const [rows, setRows] = useState(4);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const adjust = () => {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
      const lines = Math.max(4, Math.floor(el.scrollHeight / parseFloat(el.style.fontSize || "14px")));
      setRows(lines);
    };
    adjust();
    el.addEventListener("input", adjust);
    return () => el.removeEventListener("input", adjust);
  }, [value]);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };

  const expand = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <div className="review-note-editor">
      <textarea
        ref={textareaRef}
        id="review-note"
        className="review-note-input"
        value={value}
        onChange={handleInput}
        onInput={expand}
        placeholder={placeholder}
        rows={rows}
        data-testid="review-note"
        aria-label={placeholder}
      />
      <button
        type="button"
        className="review-note-expand"
        onClick={expand}
        aria-label="Expand note editor"
        data-testid="review-note-expand"
        ref={buttonRef}
      >
        Expand
      </button>
    </div>
  );
}
