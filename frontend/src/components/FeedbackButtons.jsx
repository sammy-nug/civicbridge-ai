import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { sendFeedback } from "../services/api.js";

export default function FeedbackButtons({ responseId }) {
  const [state, setState] = useState("idle"); // idle | commenting | sending | done | error
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  async function submit(rating, text) {
    setState("sending");
    try {
      await sendFeedback(responseId, rating, text);
      setState("done");
    } catch (problem) {
      setError(problem.message);
      setState("error");
    }
  }

  if (state === "done") return <p role="status" className="text-sm text-green-900">Thank you. Your feedback was recorded.</p>;

  if (state === "commenting") {
    const inputId = `feedback-${responseId}`;
    return (
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit("not_helpful", comment.trim());
        }}
      >
        <label htmlFor={inputId} className="block text-sm font-medium">
          What was wrong? (optional. Please don't include personal details.)
        </label>
        <textarea id={inputId} className="field text-sm" rows={2} maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
        <div className="flex gap-2">
          <button type="submit" className="btn-primary !min-h-[40px] !py-1.5 text-sm">Send feedback</button>
          <button type="button" className="btn-outline !min-h-[40px] !py-1.5 text-sm" onClick={() => setState("idle")}>Cancel</button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-slate-700">Was this helpful?</span>
      <button type="button" disabled={state === "sending"} onClick={() => submit("helpful")} className="btn-outline !min-h-[40px] !px-3 !py-1 text-sm">
        <ThumbsUp aria-hidden="true" size={16} /> Yes
      </button>
      <button type="button" disabled={state === "sending"} onClick={() => setState("commenting")} className="btn-outline !min-h-[40px] !px-3 !py-1 text-sm">
        <ThumbsDown aria-hidden="true" size={16} /> No, or incorrect
      </button>
      {state === "error" && <span role="alert" className="text-red-800">{error}</span>}
    </div>
  );
}
