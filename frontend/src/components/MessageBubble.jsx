import { useState } from "react";
import { AlertTriangle, CheckCircle2, CircleSlash, History, Info, RotateCcw } from "lucide-react";
import FeedbackButtons from "./FeedbackButtons.jsx";
import SourceCitation from "./SourceCitation.jsx";

const STATUS = {
  supported: { icon: CheckCircle2, text: "Based on the latest official sources we hold", className: "text-green-900" },
  outdated_only: { icon: History, text: "Based only on older documents: please confirm", className: "text-amber-900" },
  insufficient: { icon: CircleSlash, text: "Could not be verified", className: "text-slate-800" },
  declined: { icon: Info, text: "Outside what CivicBridge AI can do", className: "text-slate-800" },
  passages_only: { icon: AlertTriangle, text: "Official passages only: no AI answer", className: "text-amber-900" },
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
      <div className="flex justify-end">
        <p lang={message.language} className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-navy px-4 py-2.5 text-white">
          <span className="sr-only">You said: </span>{message.text}
        </p>
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
    <article aria-label="CivicBridge AI answer" className="space-y-3">
      <div className="card p-4">
        <p className={`mb-2 flex items-center gap-1.5 text-sm font-semibold ${status.className}`}>
          <StatusIcon aria-hidden="true" size={16} /> {status.text}
        </p>
        <p lang={response.answered_in} className="whitespace-pre-wrap break-words">
          <AnswerText text={response.answer} anchorPrefix={anchorPrefix} />
        </p>
        {response.notices.map((notice) => (
          <p key={notice} className="mt-3 flex gap-1.5 rounded-lg bg-amber-50 p-2 text-sm text-amber-950">
            <Info aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
            <span>{notice}</span>
          </p>
        ))}
        {response.english_answer && (
          <div className="mt-3">
            <button type="button" className="text-sm font-medium text-blue-800 underline" aria-expanded={showEnglish} onClick={() => setShowEnglish(!showEnglish)}>
              {showEnglish ? "Hide English version" : "Show English version"}
            </button>
            {showEnglish && (
              <p lang="en" className="mt-1 whitespace-pre-wrap rounded-lg bg-slate-100 p-2 text-sm">
                <AnswerText text={response.english_answer} anchorPrefix={anchorPrefix} />
              </p>
            )}
          </div>
        )}
      </div>

      {response.citations.length > 0 && (
        <section aria-label="Sources for this answer">
          <h2 className="mb-1.5 text-sm font-semibold">Sources</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {response.citations.map((citation) => (
              <SourceCitation key={citation.number} citation={citation} anchorPrefix={anchorPrefix} lite={lite} />
            ))}
          </ul>
        </section>
      )}
      <FeedbackButtons responseId={response.response_id} />
    </article>
  );
}
