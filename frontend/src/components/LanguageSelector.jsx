import { Languages } from "lucide-react";
import { LANGUAGE_OPTIONS } from "../i18n.js";

export default function LanguageSelector({ value, onChange, id = "language" }) {
  return (
    <div className="flex min-w-0 max-w-full items-center gap-2">
      <Languages aria-hidden="true" size={18} />
      <label htmlFor={id} className="text-sm font-medium">Language</label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[44px] w-48 min-w-0 max-w-full shrink rounded-lg border border-slate-500 bg-white px-2 font-medium text-navy"
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
