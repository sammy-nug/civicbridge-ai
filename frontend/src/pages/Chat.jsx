import { useRef, useState } from "react";
import { Plus, Send, ShieldAlert } from "lucide-react";
import ChatWindow from "../components/ChatWindow.jsx";
import LanguageSelector from "../components/LanguageSelector.jsx";
import { CHAT_TEXT, LANGUAGE_OPTIONS } from "../i18n.js";
import { sendChat } from "../services/api.js";

const MAX_LENGTH = 1000;
let nextId = 1;

// The conversation state lives in App, so moving between pages doesn't lose it.
export default function Chat({ chat, setChat, language, setLanguage, lite }) {
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const lastQuestion = useRef(null);
  const inputRef = useRef(null);
  const text = CHAT_TEXT[language];
  const languageOption = LANGUAGE_OPTIONS.find((option) => option.code === language);

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
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3">
        <h1 className="text-xl font-bold">Ask CivicBridge</h1>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
          <LanguageSelector value={language} onChange={setLanguage} />
          <button type="button" onClick={startNewConversation} className="btn-outline !px-3 text-sm">
            <Plus aria-hidden="true" size={16} /> New conversation
          </button>
        </div>
      </div>

      {!languageOption.reviewed && (
        <p className="mb-3 flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-sm text-amber-950">
          <ShieldAlert aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
          <span>
            <strong>{languageOption.label} has not yet passed human evaluation.</strong> Answers are machine translated and may contain errors.
            You can open the English version on each answer.
          </span>
        </p>
      )}

      <div className="flex-1">
        {chat.messages.length === 0 ? (
          <section aria-labelledby="suggested-heading" className="py-4">
            <p className="max-w-prose">
              Ask a question about voting and elections in Nigeria. Answers come from official documents, and each one shows its sources.
              If I can't verify something, I'll tell you.
            </p>
            <h2 id="suggested-heading" className="mb-2 mt-5 font-semibold">Try asking</h2>
            <ul lang={language} className="grid gap-2 sm:grid-cols-2">
              {text.suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button type="button" onClick={() => ask(suggestion)}
                    className="card min-h-[44px] w-full p-3 text-left font-medium hover:border-civic-blue hover:bg-blue-50">
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <ChatWindow messages={chat.messages} loading={loading} lite={lite} onRetry={() => ask(lastQuestion.current, false)} />
        )}
      </div>

      <form
        className="sticky bottom-0 mt-4 border-t border-slate-200 bg-civic-bg pb-3 pt-3"
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
            rows={2}
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
            className="field resize-none"
          />
          <button type="submit" disabled={loading || !draft.trim()} className="btn-primary shrink-0">
            <Send aria-hidden="true" size={18} />
            <span lang={language}>{text.send}</span>
          </button>
        </div>
        <p className="mt-1.5 text-xs text-slate-700">
          Never share your PVC number, NIN or passwords. Your message is sent to Google's Gemini AI, and Google's reviewers may read it, so leave out names, addresses and other personal details. CivicBridge AI is independent and is not INEC. AI can make mistakes.
        </p>
      </form>
    </div>
  );
}
