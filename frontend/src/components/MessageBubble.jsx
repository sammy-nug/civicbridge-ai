import { useState } from "react";
import { AlertTriangle, CheckCircle2, CircleSlash, History, Info, RotateCcw } from "lucide-react";
import FeedbackButtons from "./FeedbackButtons.jsx";
import SourceCitation from "./SourceCitation.jsx";

// The verification result is the first thing read, so it heads the answer as a coloured band.
const STATUS = {
  supported: { icon: CheckCircle2, text: "Based on the latest official sources we hold", className: "bg-civic-tint text-civic-greenDark" },
  outdated_only: { icon: History, text: "Based only on older documents: please confirm", className: "bg-amber-100 text-amber-950" },
  insufficient: { icon: CircleSlash, text: "Could not be verified", className: "bg-slate-200 text-slate-900" },
  declined: { icon: Info, text: "Outside what CivicBridge AI can do", className: "bg-slate-200 text-slate-900" },
  passages_only: { icon: AlertTriangle, text: "Official passages only: no AI answer", className: "bg-amber-100 text-amber-950" },
};

// Renders "[2]" as a link to source card 2. Text is never injected as HTML.
export function AnswerText({ text, anchorPrefix }) {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return <span key={index}>{part}</span>;
    return (
      <a key={index} href={`#${anchorPrefix}-${match[1]}`} aria-label={`Source ${match[1]}`}
        className="mx-0.5 rounded bg-blue-100 px-1 text-sm font-semibold text-blue-900 no-underline hover:bg-blue-200">
        {match[1]}
      </a>
    );
  });
}

export default function MessageBubble({ message, lite, onRetry }) {
  const [showEnglish, setShowEnglish] = useState(false);

  if (message.role === "user") {
    return (
      <div className="border-l-4 border-ink pl-3">
        <p className="text-sm font-semibold text-slate-700">Your question</p>
        <p lang={message.language} className="whitespace-pre-wrap break-words font-semibold">{message.text}</p>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div role="alert" className="card border-red-300 bg-red-50 p-4">
        <p className="flex gap-2 text-red-900"><AlertTriangle aria-hidden="true" className="shrink-0" size={20} />{message.text}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-outline mt-3 !min-h-[40px] text-sm">
            <RotateCcw aria-hidden="true" size={16} /> Try again
          </button>
        )}
      </div>
    );
  }

  const { response } = message;
  const status = STATUS[response.evidence_status];
  const StatusIcon = status.icon;
  const anchorPrefix = `r-${response.response_id.slice(0, 8)}`;

  return (
    <article aria-label="CivicBridge AI answer" className="card overflow-hidden">
      <p className={`flex items-center gap-1.5 px-4 py-2 text-sm font-semibold ${status.className}`}>
        <StatusIcon aria-hidden="true" size={16} className="shrink-0" /> {status.text}
      </p>
      <div className="p-4">
        <p lang={response.answered_in} className="whitespace-pre-wrap break-words">
          <AnswerText text={response.answer} anchorPrefix={anchorPrefix} />
        </p>
        {response.notices.map((notice) => (
          <p key={notice} className="mt-3 flex gap-1.5 rounded bg-amber-50 p-2 text-sm text-amber-950">
            <Info aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
            <span>{notice}</span>
          </p>
        ))}
        {response.english_answer && (
          <div className="mt-3">
            <button type="button" className="text-link min-h-[32px] text-sm" aria-expanded={showEnglish} onClick={() => setShowEnglish(!showEnglish)}>
              {showEnglish ? "Hide English version" : "Show English version"}
            </button>
            {showEnglish && (
              <p lang="en" className="mt-1 whitespace-pre-wrap rounded bg-paper p-2 text-sm">
                <AnswerText text={response.english_answer} anchorPrefix={anchorPrefix} />
              </p>
            )}
          </div>
        )}
      </div>

      {response.citations.length > 0 && (
        <section aria-label="Sources for this answer" className="border-t border-rule px-4 pt-3">
          <h2 className="font-sans text-sm font-semibold">Sources ({response.citations.length})</h2>
          <ul className="divide-y divide-rule">
            {response.citations.map((citation) => (
              <SourceCitation key={citation.number} citation={citation} anchorPrefix={anchorPrefix} lite={lite} />
            ))}
          </ul>
        </section>
      )}
      <div className="border-t border-rule bg-paper px-4 py-2.5">
        <FeedbackButtons responseId={response.response_id} />
      </div>
    </article>
  );
}
