import { useState } from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, Search, XCircle } from "lucide-react";
import LanguageSelector from "../components/LanguageSelector.jsx";
import LoadingIndicator from "../components/LoadingIndicator.jsx";
import SourceCitation from "../components/SourceCitation.jsx";
import FeedbackButtons from "../components/FeedbackButtons.jsx";
import { AnswerText } from "../components/MessageBubble.jsx";
import { LANGUAGE_OPTIONS } from "../i18n.js";
import { verifyClaim } from "../services/api.js";

const RESULT = {
  supported: { label: "Supported by available official sources", icon: CheckCircle2, className: "border-green-700 bg-green-50 text-green-950" },
  contradicted: { label: "Contradicted by available official sources", icon: XCircle, className: "border-red-700 bg-red-50 text-red-950" },
  insufficient_evidence: { label: "Insufficient evidence to determine", icon: HelpCircle, className: "border-slate-500 bg-slate-100 text-slate-900" },
};

function FindingList({ title, items, language }) {
  if (!items.length) return null;
  return (
    <section>
      <h3 className="font-semibold">{title}</h3>
      <ul lang={language} className="mt-1 list-disc space-y-1 pl-5">
        {items.map((item) => <li key={item}><AnswerText text={item} anchorPrefix="claim-source" /></li>)}
      </ul>
    </section>
  );
}

export default function Verify({ language, setLanguage, lite }) {
  const [claim, setClaim] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const languageOption = LANGUAGE_OPTIONS.find((option) => option.code === language);

  async function submit(event) {
    event.preventDefault();
    if (claim.trim().length < 5 || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await verifyClaim(claim.trim(), language));
    } catch (problem) {
      setError(problem.message);
    } finally {
      setLoading(false);
    }
  }

  const outcome = result && RESULT[result.assessment];
  const OutcomeIcon = outcome?.icon;

  return (
    <div className="page max-w-3xl">
      <p className="eyebrow">Compare with official sources</p>
      <h1 className="mt-1 text-3xl font-bold">Check Electoral Information</h1>
      <p className="mt-2 max-w-prose">
        Heard something about voting or election rules? Paste it here and we'll compare it with the official documents in our library.
        We check the statement, not the person who shared it.
      </p>

      <form onSubmit={submit} className="card mt-6 space-y-3 p-4">
        <div>
          <label htmlFor="claim" className="mb-1 block font-medium">Statement or question to check</label>
          <textarea
            id="claim"
            rows={3}
            maxLength={1000}
            className="field"
            lang={language}
            value={claim}
            onChange={(event) => setClaim(event.target.value)}
            placeholder="For example: You can vote with a temporary voter's card."
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <LanguageSelector id="verify-language" value={language} onChange={setLanguage} />
          <button type="submit" className="btn-primary" disabled={loading || claim.trim().length < 5}>
            <Search aria-hidden="true" size={18} /> Check information
          </button>
        </div>
        <p className="text-xs text-slate-700">Your message is sent to Google's Gemini AI, and Google's reviewers may read it, so leave out names, addresses and other personal details.</p>
        {!languageOption.reviewed && (
          <p className="text-sm text-amber-950"><strong>{languageOption.label} has not yet passed human evaluation.</strong> Results are machine translated and may contain errors.</p>
        )}
      </form>

      <div aria-live="polite" className="mt-6 space-y-4">
        {loading && <LoadingIndicator label="Comparing with official sources" />}
        {error && (
          <p role="alert" className="card flex gap-2 border-red-300 bg-red-50 p-4 text-red-900">
            <AlertTriangle aria-hidden="true" size={20} className="shrink-0" /> {error}
          </p>
        )}
        {result && (
          <>
            <div className={`rounded-xl border-l-4 p-4 ${outcome.className}`}>
              <h2 className="flex items-center gap-2 text-lg font-bold">
                <OutcomeIcon aria-hidden="true" size={22} className="shrink-0" /> {outcome.label}
              </h2>
              <p lang={result.answered_in} className="mt-2"><AnswerText text={result.explanation} anchorPrefix="claim-source" /></p>
            </div>
            <div className="card space-y-4 p-4">
              <FindingList title="What the evidence supports" items={result.supports} language={result.answered_in} />
              <FindingList title="What the evidence contradicts" items={result.contradicts} language={result.answered_in} />
              <FindingList title="What cannot be established" items={result.cannot_establish} language={result.answered_in} />
              <FindingList title="Limitations of this check" items={result.limitations} language={result.answered_in} />
            </div>
            {result.supporting_sources.length > 0 && (
              <section>
                <h2 className="mb-2 font-semibold">Sources</h2>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {result.supporting_sources.map((citation) => (
                    <SourceCitation key={citation.number} citation={citation} anchorPrefix="claim-source" lite={lite} />
                  ))}
                </ul>
              </section>
            )}
            <FeedbackButtons responseId={result.response_id} />
          </>
        )}
      </div>
    </div>
  );
}
