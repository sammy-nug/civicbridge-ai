import { useState } from "react";
import { AlertTriangle, ChevronDown, ExternalLink, FileText } from "lucide-react";

export const STATUS_LABELS = {
  current: { text: "Latest we hold", className: "bg-green-100 text-green-900" },
  needs_verification: { text: "Older: check for changes", className: "bg-amber-100 text-amber-900" },
  historical: { text: "Historical", className: "bg-slate-200 text-slate-800" },
  superseded: { text: "Replaced by newer edition", className: "bg-slate-200 text-slate-800" },
};

function locationText(citation) {
  if (citation.page) return `Page ${citation.page}`;
  return citation.section || "Web page";
}

// PDF viewers understand #page=N, so a citation opens on the page it refers to.
function sourceLink(citation) {
  const isPdf = citation.url.toLowerCase().includes(".pdf");
  return isPdf && citation.page ? `${citation.url}#page=${citation.page}` : citation.url;
}

export default function SourceCitation({ citation, anchorPrefix = "source", lite = false }) {
  const [expanded, setExpanded] = useState(!lite);
  const status = STATUS_LABELS[citation.status] || STATUS_LABELS.historical;
  const passageId = `${anchorPrefix}-${citation.number}-passage`;

  return (
    <li id={`${anchorPrefix}-${citation.number}`} className="card scroll-mt-24 p-3 text-sm">
      <div className="flex items-start gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-navy text-xs font-bold text-white">
          {citation.number}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug">{citation.title}</p>
          <p className="text-slate-700">{citation.organisation}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-slate-700">
            <span className="inline-flex items-center gap-1"><FileText aria-hidden="true" size={14} />{locationText(citation)}</span>
            <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${status.className}`}>{status.text}</span>
          </p>
          <p className="mt-1 text-xs text-slate-700">
            Published: {citation.publication_date || "date not stated"} · Retrieved: {citation.retrieved_date}
          </p>
          {citation.notes.map((note) => (
            <p key={note} className="mt-1 flex gap-1 text-xs text-amber-900">
              <AlertTriangle aria-hidden="true" size={14} className="mt-0.5 shrink-0" />
              <span>{note}</span>
            </p>
          ))}
          <button
            type="button"
            className="mt-2 inline-flex min-h-[32px] items-center gap-1 font-medium text-blue-800 underline"
            aria-expanded={expanded}
            aria-controls={passageId}
            onClick={() => setExpanded(!expanded)}
          >
            <ChevronDown aria-hidden="true" size={14} className={expanded ? "rotate-180" : ""} />
            {expanded ? "Hide passage" : "Show passage"}
          </button>
          <blockquote id={passageId} hidden={!expanded} className="mt-1 border-l-2 border-slate-300 pl-2 text-slate-800">
            {citation.excerpt}
          </blockquote>
          <a
            href={sourceLink(citation)}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex min-h-[32px] items-center gap-1 font-medium text-blue-800 underline"
          >
            Open official source <ExternalLink aria-hidden="true" size={14} />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </div>
      </div>
    </li>
  );
}
