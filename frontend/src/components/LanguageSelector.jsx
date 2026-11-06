import { Languages } from "lucide-react";
import { LANGUAGE_OPTIONS } from "../i18n.js";

export default function LanguageSelector({ value, onChange, id = "language", compact = false }) {
  return (
    <div className="flex min-w-0 max-w-full items-center gap-2">
      <Languages aria-hidden="true" size={18} className={compact ? "hidden shrink-0 sm:block" : "shrink-0"} />
      <label htmlFor={id} className={compact ? "sr-only sm:not-sr-only sm:text-sm sm:font-medium" : "text-sm font-medium"}>Language</label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`min-h-[44px] min-w-0 max-w-full shrink rounded border border-slate-600 bg-white px-2 font-medium text-ink ${compact ? "w-32 sm:w-48" : "w-48"}`}
      >
        {LANGUAGE_OPTIONS.map((option) => (
          <option key={option.code} value={option.code}>
            {option.label}{option.reviewed ? "" : " (not reviewed)"}
          </option>
        ))}
      </select>
    </div>
  );
}
