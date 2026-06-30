"use client";

import { useState } from "react";
import { FlaskConical, Square } from "lucide-react";

const PLACEHOLDER =
  "e.g. 65-year-old male, type 2 diabetes, HbA1c 9.2%, on metformin. Considering adding an SGLT2 inhibitor. What is the cardiovascular benefit evidence?";

export function QueryForm({
  onSubmit,
  onCancel,
  running,
}: {
  onSubmit: (clinicalText: string) => void;
  onCancel: () => void;
  running: boolean;
}) {
  const [text, setText] = useState("");

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
          Clinical case
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={6}
          className="focus-ring w-full resize-y rounded-xl border border-slate-200 bg-white p-3.5 text-sm leading-relaxed text-slate-800 placeholder:text-slate-400"
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          disabled={running || !text.trim()}
          onClick={() => onSubmit(text)}
          className="btn-primary"
        >
          <FlaskConical className="h-4 w-4" />
          {running ? "Running…" : "Run evidence query"}
        </button>
        {running && (
          <button onClick={onCancel} className="btn-ghost">
            <Square className="h-3.5 w-3.5" />
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
