import { Link } from "react-router-dom";

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-bold">{title}</h2>
      <div className="mt-2 space-y-3">{children}</div>
    </section>
  );
}

export default function About() {
  return (
    <div className="page max-w-3xl">
      <p className="eyebrow">About</p>
      <h1 className="mt-1 text-3xl font-bold">Making electoral information understandable</h1>
      <p className="mt-3 rounded-lg border border-slate-300 bg-white p-3">
        CivicBridge AI is an independent project built for the AI4Elections Hackathon. It is not run by, affiliated with or endorsed by INEC, any government body or any political party.
      </p>

      <Section title="The problem">
        <p>Many Nigerians have simple questions about voting but must search long documents and several websites to answer them. Language barriers, limited digital access, fragmented information and misinformation make this harder.</p>
      </Section>

      <Section title="Our mission">
        <p>To help every Nigerian find and understand reliable electoral information, in plain language, with sources they can check for themselves.</p>
      </Section>

      <Section title="How the AI works">
        <ol className="list-decimal space-y-1.5 pl-6">
          <li>Your question is prepared for searching. If it isn't in English, it's translated for the search, because the documents are in English.</li>
          <li>The system finds the most relevant passages from official documents and drops weak matches. If nothing is relevant enough, it says it can't verify an answer.</li>
          <li>An AI model writes an answer using only those passages and marks which passage supports each statement.</li>
          <li>The answer is checked automatically. Citations must match passages we actually retrieved, and numbers must appear in those passages. If not, the answer isn't shown.</li>
          <li>If you chose Hausa, Yoruba or Igbo, the checked answer is translated and checked again. If that fails, you get the English answer with a notice.</li>
        </ol>
        <p>These checks reduce errors, but they can't remove them all. Please confirm important details with INEC.</p>
      </Section>

      <Section title="Data sources">
        <p>We use public documents and pages from INEC's official websites, including the Electoral Act 2026 and the 2026 Regulations and Guidelines. We keep each document's link and retrieval date, and label older documents.</p>
        <p>Our library is a snapshot, so it may miss very recent announcements. <Link to="/resources" className="font-medium text-blue-800 underline">See all our documents.</Link></p>
      </Section>

      <Section title="Responsible AI principles">
        <ul className="list-disc space-y-1.5 pl-6">
          <li>Political neutrality: no candidate recommendations, party endorsements or persuasion.</li>
          <li>No political profiling and no predictions of election results.</li>
          <li>No invented procedures, and no unsupported claims presented as facts.</li>
          <li>Statements are checked, not people. Not finding something is never treated as proof that it's false.</li>
          <li>Translations are labelled until they have passed human evaluation. None of our Nigerian-language translations have yet.</li>
        </ul>
      </Section>

      <Section title="Privacy commitments">
        <ul className="list-disc space-y-1.5 pl-6">
          <li>No accounts, and no advertising or tracking cookies.</li>
          <li>We never ask for your PVC number, NIN or passwords. If you type them by mistake, we try to remove them before processing. This automatic removal can miss things, so please don't enter them.</li>
          <li>We don't store your questions or the answers. Recent turns are kept in memory for up to 30 minutes so follow-up questions work.</li>
          <li>We store basic response records (language, outcome, speed) and any feedback you choose to send.</li>
          <li>Your question, with identity details removed, is sent to an AI model provider to generate the answer. On free plans, the provider may use it to improve its products, and its staff may read it. Please don't include personal details.</li>
        </ul>
      </Section>
    </div>
  );
}
