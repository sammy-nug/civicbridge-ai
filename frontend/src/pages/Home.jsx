import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpenCheck, FileSearch, Languages, MessageCircleQuestion, Scale, ShieldCheck, UserX } from "lucide-react";
import { getResources } from "../services/api.js";
import { LANGUAGE_OPTIONS } from "../i18n.js";

const STEPS = [
  { icon: MessageCircleQuestion, title: "You ask", body: "Type a question in plain language. There's no sign-up, and we don't need your name." },
  { icon: FileSearch, title: "We search official documents", body: "CivicBridge finds the most relevant passages in electoral documents from official sources." },
  { icon: BookOpenCheck, title: "You get an answer with sources", body: "The AI answers only from those passages. You can open each source and check it yourself." },
];

const SAFEGUARDS = [
  { icon: Scale, title: "Strictly nonpartisan", body: "We never recommend candidates or parties, try to persuade you, or predict results." },
  { icon: ShieldCheck, title: "Says when it doesn't know", body: "If the official documents don't answer your question, CivicBridge tells you rather than guessing." },
  { icon: UserX, title: "Your privacy comes first", body: "We never ask for your PVC number or NIN, and we remove them if they're typed in by mistake." },
];

export default function Home({ lite }) {
  const [documentCount, setDocumentCount] = useState(null);
  useEffect(() => {
    if (lite) return;
    getResources().then((data) => setDocumentCount(data.total)).catch(() => {});
  }, [lite]);

  return (
    <>
      <section className="on-dark bg-navy text-white">
        <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6 sm:py-20">
          <h1 className="max-w-3xl text-4xl font-bold leading-tight sm:text-5xl">Electoral Information Should Be Accessible to Everyone.</h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-200">
            Ask questions, understand electoral processes and access trusted civic information in a language you understand.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link to="/chat" className="btn-green text-lg">Ask CivicBridge</Link>
            <Link to="/verify" className="btn-on-dark text-lg">Check Electoral Information</Link>
          </div>
          <p className="mt-6 text-sm text-slate-300">
            Independent civic education project. Not affiliated with INEC.
            {documentCount ? ` Drawing on ${documentCount} official documents.` : ""}
          </p>
        </div>
        <svg className="decorative block h-10 w-full text-civic-bg" viewBox="0 0 1200 60" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 60 C 300 -10, 900 -10, 1200 60 Z" fill="currentColor" />
        </svg>
      </section>

      <section aria-labelledby="languages-heading" className="page !py-8">
        <div className="card flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <h2 id="languages-heading" className="flex items-center gap-2 font-semibold"><Languages aria-hidden="true" /> Supported languages</h2>
          <ul className="flex flex-wrap gap-2">
            {LANGUAGE_OPTIONS.map((option) => (
              <li key={option.code} className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium">
                {option.label}{option.reviewed ? "" : " · not yet human-reviewed"}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="how-heading" className="page !pt-2">
        <h2 id="how-heading" className="text-2xl font-bold">How it works</h2>
        <ol className="mt-5 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="card p-5">
              <step.icon aria-hidden="true" className="text-civic-blue" />
              <h3 className="mt-3 font-semibold">{index + 1}. {step.title}</h3>
              <p className="mt-1 text-slate-800">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="sources-heading" className="bg-white">
        <div className="page">
          <h2 id="sources-heading" className="text-2xl font-bold">Why trusted sources matter</h2>
          <div className="mt-3 max-w-prose space-y-3">
            <p>
              Electoral rules change, and old information can cost someone their vote. A deadline in one year's guide may not apply in the next.
            </p>
            <p>
              That's why each answer shows where it came from and when that source was published. Older documents are clearly labelled, and current ones are preferred.
            </p>
          </div>
          <Link to="/resources" className="btn-outline mt-5">See the documents we use</Link>
        </div>
      </section>

      <section aria-labelledby="ai-heading" className="page">
        <h2 id="ai-heading" className="text-2xl font-bold">Responsible AI</h2>
        <ul className="mt-5 grid gap-4 md:grid-cols-3">
          {SAFEGUARDS.map((item) => (
            <li key={item.title} className="card p-5">
              <item.icon aria-hidden="true" className="text-green-800" />
              <h3 className="mt-3 font-semibold">{item.title}</h3>
              <p className="mt-1 text-slate-800">{item.body}</p>
            </li>
          ))}
        </ul>
        <Link to="/about" className="mt-5 inline-block font-medium text-blue-800 underline">Read more about how CivicBridge AI works</Link>
      </section>
    </>
  );
}
