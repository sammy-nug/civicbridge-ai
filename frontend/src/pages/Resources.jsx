import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ExternalLink, Search } from "lucide-react";
import LoadingIndicator from "../components/LoadingIndicator.jsx";
import { STATUS_LABELS } from "../components/SourceCitation.jsx";
import { getResources } from "../services/api.js";

export default function Resources() {
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setError("");
    getResources().then((data) => setDocuments(data.documents)).catch((problem) => setError(problem.message));
  }, [attempt]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!documents || !needle) return documents || [];
    return documents.filter((doc) =>
      `${doc.title} ${doc.organisation} ${doc.description} ${doc.category}`.toLowerCase().includes(needle)
    );
  }, [documents, query]);

  return (
    <div className="page">
      <p className="eyebrow">Our knowledge base</p>
      <h1 className="mt-1 text-3xl font-bold">Official electoral documents</h1>
      <p className="mt-2 max-w-prose">
        These are the documents CivicBridge AI can draw on. Each was downloaded from its official source and checked. Older documents are labelled so they aren't mistaken for current rules.
      </p>

      <div className="relative mt-6 max-w-lg">
        <label htmlFor="resource-search" className="mb-1 block font-medium">Search documents</label>
        <Search aria-hidden="true" size={18} className="absolute bottom-3.5 left-3 text-slate-600" />
        <input id="resource-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} className="field pl-9" placeholder="Try: registration, observer, 2026" />
      </div>

      <div className="mt-6">
        {error && (
          <div role="alert" className="card border-red-300 bg-red-50 p-4 text-red-900">
            <p className="flex gap-2"><AlertTriangle aria-hidden="true" size={20} className="shrink-0" />{error}</p>
            <button type="button" className="btn-outline mt-3 !min-h-[40px] text-sm" onClick={() => setAttempt(attempt + 1)}>Try again</button>
          </div>
        )}
        {!documents && !error && <LoadingIndicator label="Loading documents" />}
        {documents && (
          <>
            <p role="status" className="mb-3 text-sm text-slate-700">Showing {filtered.length} of {documents.length} documents</p>
            <ul className="grid gap-3 md:grid-cols-2">
              {filtered.map((doc) => {
                const status = STATUS_LABELS[doc.status] || STATUS_LABELS.historical;
                return (
                  <li key={doc.id} className="card flex flex-col p-4">
                    <span className={`w-fit rounded px-1.5 py-0.5 text-xs font-semibold ${status.className}`}>{status.text}</span>
                    <h2 className="mt-2 font-semibold leading-snug">{doc.title}</h2>
                    <p className="text-sm text-slate-700">{doc.organisation}</p>
                    <p className="mt-2 flex-1 text-sm">{doc.description}</p>
                    <p className="mt-2 text-xs text-slate-700">
                      Published: {doc.publication_date || "date not stated"}
                      {doc.publication_date_basis ? ` (${doc.publication_date_basis.toLowerCase()})` : ""} · Retrieved: {doc.retrieved_date}
                    </p>
                    <a href={doc.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex min-h-[32px] items-center gap-1 text-sm font-medium text-blue-800 underline">
                      Official source <ExternalLink aria-hidden="true" size={14} /><span className="sr-only">(opens in a new tab)</span>
                    </a>
                  </li>
                );
              })}
            </ul>
            {filtered.length === 0 && <p>No documents match “{query}”.</p>}
          </>
        )}
      </div>
    </div>
  );
}
