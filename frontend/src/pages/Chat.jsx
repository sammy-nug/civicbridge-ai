import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Plus, Send, ShieldAlert } from "lucide-react";
import ChatWindow from "../components/ChatWindow.jsx";
import LanguageSelector from "../components/LanguageSelector.jsx";
import { CHAT_TEXT, LANGUAGE_OPTIONS } from "../i18n.js";
import { sendChat } from "../services/api.js";

const MAX_LENGTH = 1000;
const SHOW_COUNT_FROM = 900;
const MAX_INPUT_HEIGHT = 160;
let nextId = 1;

// The conversation state lives in App, so moving between pages doesn't lose it.
export default function Chat({ chat, setChat, language, setLanguage, lite }) {
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const lastQuestion = useRef(null);
  const inputRef = useRef(null);
  const text = CHAT_TEXT[language];
  const languageOption = LANGUAGE_OPTIONS.find((option) => option.code === language);
  const location = useLocation();
  const navigate = useNavigate();
  const handledNavigation = useRef(null);

  // The message box starts on one line and grows with the text, leaving room for the answers.
  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight + 2, MAX_INPUT_HEIGHT)}px`;
  }, [draft]);

  // A question asked on the home page arrives here. Clearing it stops Back from asking it again.
  useEffect(() => {
    const question = location.state?.ask;
    if (!question || handledNavigation.current === location.key) return;
    handledNavigation.current = location.key;
    navigate(location.pathname, { replace: true, state: null });
    ask(question);
  }, [location.key]); // eslint-disable-line react-hooks/exhaustive-deps

  async function ask(question, addUserMessage = true) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    lastQuestion.current = trimmed;
    setDraft("");
    setLoading(true);
    setChat((current) => ({
      ...current,
      messages: [
        ...current.messages.filter((message) => addUserMessage || message.role !== "error"),
        ...(addUserMessage ? [{ id: nextId++, role: "user", text: trimmed, language }] : []),
      ],
    }));
    try {
      const response = await sendChat(trimmed, language, chat.sessionId);
      setChat((current) => ({
        sessionId: response.session_id,
        messages: [...current.messages, { id: nextId++, role: "assistant", response }],
      }));
    } catch (error) {
      setChat((current) => ({
        ...current,
        messages: [...current.messages, { id: nextId++, role: "error", text: error.message }],
      }));
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    setChat({ sessionId: null, messages: [] });
    setDraft("");
    inputRef.current?.focus();
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-3 sm:px-6 sm:pt-5">
      <div className="flex items-center justify-between gap-2 pb-3">
        <h1 className="whitespace-nowrap text-lg font-bold sm:text-2xl">Ask CivicBridge</h1>
        <div className="flex min-w-0 items-center gap-2">
          <LanguageSelector value={language} onChange={setLanguage} compact />
          <button type="button" onClick={startNewConversation} className="btn-outline shrink-0 !px-3 text-sm">
            <Plus aria-hidden="true" size={16} /> <span className="sr-only sm:not-sr-only">New conversation</span>
          </button>
        </div>
      </div>

      {!languageOption.reviewed && (
        <p className="mb-3 flex gap-2 rounded border border-amber-400 bg-amber-50 p-2.5 text-sm text-amber-950">
          <ShieldAlert aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
          <span>
            <strong>{languageOption.label} has not yet passed human evaluation.</strong> Answers are machine translated and may contain errors.
            You can open the English version on each answer.
          </span>
        </p>
      )}

      <div className="flex-1">
        {chat.messages.length === 0 ? (
          <section aria-labelledby="suggested-heading" className="pb-2">
            <p className="max-w-prose">
              Answers come from official documents and show their sources. If something can't be verified, you'll be told.
            </p>
            <h2 id="suggested-heading" className="mt-4 font-sans font-semibold">Common questions</h2>
            <ul lang={language} className="mt-1 divide-y divide-rule border-y border-rule">
              {text.suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button type="button" onClick={() => ask(suggestion)}
                    className="flex min-h-[48px] w-full items-center justify-between gap-3 py-2 text-left font-medium text-blue-800 hover:underline">
                    {suggestion}
                    <ArrowRight aria-hidden="true" size={18} className="shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm">Heard something you're not sure about? <Link to="/verify" className="text-link">Check it against official sources</Link></p>
          </section>
        ) : (
          <ChatWindow messages={chat.messages} loading={loading} lite={lite} onRetry={() => ask(lastQuestion.current, false)} />
        )}
      </div>

      <form
        className="sticky bottom-0 z-10 mt-3 border-t border-rule bg-paper pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          ask(draft);
        }}
      >
        <label htmlFor="chat-input" className="sr-only">Your question</label>
        <div className="flex items-end gap-2">
          <textarea
            id="chat-input"
            ref={inputRef}
            lang={language}
            rows={1}
            maxLength={MAX_LENGTH}
            value={draft}
            placeholder={text.placeholder}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                ask(draft);
              }
            }}
            className="field min-h-[44px] resize-none"
          />
          <button type="submit" disabled={loading || !draft.trim()} className="btn-primary shrink-0 !px-3 sm:!px-5">
            <Send aria-hidden="true" size={18} />
            <span lang={language} className="sr-only sm:not-sr-only">{text.send}</span>
          </button>
        </div>
        {draft.length >= SHOW_COUNT_FROM && <p className="mt-1 text-right text-xs text-slate-700">{draft.length} of {MAX_LENGTH} characters</p>}
        <p className="mt-1.5 text-xs leading-snug text-slate-700">
          {chat.messages.length === 0
            ? "Leave out names, addresses, PVC numbers, NINs and passwords. Messages go to Google's Gemini AI, where Google's reviewers may read them. AI can make mistakes, so check with INEC."
            : "Leave out personal details: Google's reviewers may read messages. AI can make mistakes."}
          {" "}<Link to="/about" className="underline">Privacy</Link>
        </p>
      </form>
    </div>
  );
}
