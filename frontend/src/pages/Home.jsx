import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2, ExternalLink, FileText } from "lucide-react";
import LanguageSelector from "../components/LanguageSelector.jsx";
import { CHAT_TEXT, LANGUAGE_OPTIONS } from "../i18n.js";
import { getResources } from "../services/api.js";

// Every fact below is copied from the documents in knowledge_base/processed_documents.
// Re-check them, and CHECKED_ON, whenever the sources are refreshed: they can go out of date.
const CHECKED_ON = "5 November 2026";
const ACT_URL = "https://www.inecnigeria.org/documents/Electoral-Act-2026.pdf";
const CALENDAR_URL = "https://www.inecnigeria.org/elections/calendar";

const LATEST = [
  { label: "Presidential and National Assembly election", value: "16 January 2027", source: "INEC election calendar", href: CALENDAR_URL },
  { label: "Governorship and State House of Assembly election", value: "6 February 2027", source: "INEC election calendar", href: CALENDAR_URL },
  { label: "Continuous voter registration", value: "Ended", source: "INEC registration portal", href: "https://cvr.inecnigeria.org/" },
  { label: "Accreditation and voting on election days", value: "8:30 AM to 2:30 PM", source: "INEC election calendar", href: CALENDAR_URL },
];

const CHANGES = [
  {
    topic: "Replacing a lost or damaged voter's card",
    older: { rule: "Apply at least 7 days before the polls", source: "INEC registration guidelines, 2013", href: "https://www.inecnigeria.org/documents/resources/articles/INEC-guidelines-for-registration-of-voters.pdf#page=9" },
    current: { rule: "Apply not less than 90 days before polling day", source: "Electoral Act 2026, section 18", href: `${ACT_URL}#page=15` },
  },
  {
    topic: "Penalty for buying or selling votes",
    older: { rule: "A fine of up to ₦500,000, or 12 months in prison, or both", source: "INEC's FAQ page, citing the 2022 Act", href: "https://www.inecnigeria.org/faqs" },
    current: { rule: "A fine of not less than ₦5,000,000, or not less than two years in prison, or both", source: "Electoral Act 2026, section 22", href: `${ACT_URL}#page=16` },
  },
];

const CHECKS = [
  ["Search", "Your question is matched against official documents. If nothing relevant is found, you are told so and no AI is used."],
  ["Answer from the passages", "The AI writes an answer using only the passages found, and marks which passage supports each statement."],
  ["Check before showing", "Software checks that each citation is real and that numbers appear in the cited passage. If not, no answer is shown."],
  ["Show the source", "You see the document, the page and the date we retrieved it, so you can read the original yourself."],
];

const WILL_NOT = [
  "Tell you who to vote for, or compare candidates and parties",
  "Predict who will win an election",
  "Guess when the documents don't give an answer",
  "Ask for your PVC number, NIN or password",
];

function SourceLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-link inline-flex items-baseline gap-1 text-sm">
      {children}
      <ExternalLink aria-hidden="true" size={12} className="shrink-0" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

function ExampleAnswer() {
  return (
    <figure className="card overflow-hidden">
      <figcaption className="border-b border-rule bg-paper px-4 py-2 text-sm font-semibold">
        Example: what an answer looks like
      </figcaption>
      <div className="p-4">
        <p className="font-serif text-lg font-bold">How can I replace a lost PVC?</p>
        <p className="mt-2 flex items-center gap-1.5 text-sm font-semibold text-civic-greenDark">
          <CheckCircle2 aria-hidden="true" size={16} /> Based on the latest official sources we hold
        </p>
        <p className="mt-2">
          Apply in person to the electoral officer, or another authorised officer, not less than 90 days before polling day, and explain how the card was lost. The new card is marked “REPLACEMENT”.
          <span className="mx-0.5 rounded bg-blue-100 px-1 text-sm font-semibold text-blue-900"><span className="sr-only">Source </span>1</span>
        </p>
        <div className="mt-3 flex gap-2 border-t border-rule pt-3 text-sm">
          <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-ink text-xs font-bold text-white">1</span>
          <div>
            <p className="font-semibold">Electoral Act, 2026</p>
            <p className="flex items-center gap-1 text-slate-700"><FileText aria-hidden="true" size={14} /> Section 18, page 15 · Retrieved 5 Nov 2026</p>
            <SourceLink href={`${ACT_URL}#page=15`}>Open official source</SourceLink>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-700">We wrote this example from section 18. Live answers are written by AI, so the wording varies.</p>
      </div>
    </figure>
  );
}

export default function Home({ language, setLanguage, lite }) {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [documentCount, setDocumentCount] = useState(null);
  const text = CHAT_TEXT[language];
  const languageOption = LANGUAGE_OPTIONS.find((option) => option.code === language);
  const unreviewed = LANGUAGE_OPTIONS.filter((option) => !option.reviewed).map((option) => option.label);

  useEffect(() => {
    if (lite) return;
    getResources().then((data) => setDocumentCount(data.total)).catch(() => {});
  }, [lite]);

  function askQuestion(event) {
    event.preventDefault();
    if (question.trim()) navigate("/chat", { state: { ask: question.trim() } });
  }

  return (
    <>
      <section aria-labelledby="home-heading" className="border-b border-rule bg-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-8 sm:px-6 sm:py-14 lg:grid-cols-[1.15fr_1fr] lg:items-start lg:gap-12">
          <div>
            <p className="eyebrow">Nigerian elections, from official sources</p>
            <h1 id="home-heading" className="mt-2 text-4xl font-bold sm:text-5xl">Know the rules before you vote.</h1>
            <p className="mt-4 max-w-xl text-lg">
              Ask about registration, your PVC or election day. Answers come from INEC's published documents and show the page they came from. If something can't be verified, we tell you.
            </p>
            <form onSubmit={askQuestion} className="mt-6 max-w-xl">
              <label htmlFor="home-question" className="font-semibold">What do you want to know?</label>
              <textarea
                id="home-question"
                lang={language}
                rows={2}
                maxLength={1000}
                value={question}
                placeholder={text.placeholder}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) askQuestion(event);
                }}
                className="field mt-1.5 resize-none"
              />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <LanguageSelector id="home-language" value={language} onChange={setLanguage} />
                <button type="submit" disabled={!question.trim()} className="btn-primary">Ask CivicBridge <ArrowRight aria-hidden="true" size={18} /></button>
              </div>
              {!languageOption.reviewed && (
                <p className="mt-2 text-sm text-amber-950"><strong>{languageOption.label} has not yet passed human evaluation.</strong> Answers are machine translated and may contain errors.</p>
              )}
              <p className="mt-2 text-xs text-slate-700">Leave out names, addresses, PVC numbers, NINs and passwords. Messages go to Google's Gemini AI, where Google's reviewers may read them.</p>
            </form>
            <p className="mt-5">Heard something you're not sure about? <Link to="/verify" className="text-link">Check it against official sources</Link></p>
          </div>
          <ExampleAnswer />
        </div>
      </section>

      <section aria-labelledby="latest-heading" className="page !py-8 sm:!py-10">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="latest-heading" className="text-2xl font-bold">Latest from INEC's websites</h2>
          <p className="text-sm text-slate-700">Last checked {CHECKED_ON}. Always confirm with INEC.</p>
        </div>
        <dl className="mt-4 grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
          {LATEST.map((fact) => (
            <div key={fact.label} className="flex flex-col bg-white p-4">
              <dt className="text-sm text-slate-700">{fact.label}</dt>
              <dd className="mt-1 flex flex-1 flex-col justify-between gap-1">
                <span className="font-serif text-xl font-bold">{fact.value}</span>
                <SourceLink href={fact.href}>{fact.source}</SourceLink>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="common-heading" className="page !pt-0">
        <h2 id="common-heading" className="text-2xl font-bold">Common questions</h2>
        <ul lang={language} className="mt-3 border-t border-rule md:grid md:grid-cols-2 md:gap-x-8">
          {text.suggestions.map((suggestion) => (
            <li key={suggestion} className="border-b border-rule">
              <Link to="/chat" state={{ ask: suggestion }} className="flex min-h-[48px] items-center justify-between gap-3 py-2.5 font-medium text-blue-800 hover:underline">
                {suggestion}
                <ArrowRight aria-hidden="true" size={18} className="shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="changes-heading" className="border-y border-rule bg-white">
        <div className="page">
          <h2 id="changes-heading" className="text-2xl font-bold">An old answer can cost you your vote</h2>
          <p className="mt-2 max-w-2xl">
            Old rules stay online long after the law changes. CivicBridge labels each document by date and status, and prefers the newest one. These differences are in the documents we hold:
          </p>
          <div className="mt-5 space-y-5">
            {CHANGES.map((change) => (
              <article key={change.topic} className="border-t-2 border-ink pt-3">
                <h3 className="font-semibold">{change.topic}</h3>
                <div className="mt-2 grid gap-3 md:grid-cols-2 md:gap-6">
                  <div>
                    <p className="text-sm font-semibold text-slate-700">Older source</p>
                    <p className="mt-0.5">{change.older.rule}</p>
                    <SourceLink href={change.older.href}>{change.older.source}</SourceLink>
                  </div>
                  <div className="border-l-4 border-civic-green pl-3">
                    <p className="text-sm font-semibold text-civic-greenDark">Current law</p>
                    <p className="mt-0.5 font-semibold">{change.current.rule}</p>
                    <SourceLink href={change.current.href}>{change.current.source}</SourceLink>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="checks-heading" className="page grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <h2 id="checks-heading" className="text-2xl font-bold">How each answer is checked</h2>
          <ol className="mt-4 space-y-4">
            {CHECKS.map(([title, body], index) => (
              <li key={title} className="flex gap-3">
                <span aria-hidden="true" className="w-7 shrink-0 font-serif text-2xl font-bold leading-tight text-civic-green">{index + 1}</span>
                <div>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-0.5">{body}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-sm text-slate-700">These checks reduce errors, but they can't remove them all. <Link to="/about" className="text-link">Read how it works and what we do with your data</Link></p>
        </div>
        <div>
          <h2 className="text-2xl font-bold">What it will not do</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5">
            {WILL_NOT.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <h2 className="mt-8 text-2xl font-bold">What it's built on</h2>
          <p className="mt-3">{documentCount ? `${documentCount} official` : "Official"} documents and pages, each labelled by date and status.</p>
          <Link to="/resources" className="btn-outline mt-3">Browse the documents</Link>
          <p className="mt-5 text-sm text-slate-700">Available in English, {unreviewed.join(", ")}. Nigerian-language translations are machine-generated and have not yet been reviewed by people.</p>
        </div>
      </section>
    </>
  );
}
