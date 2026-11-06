import { useEffect, useRef } from "react";
import LoadingIndicator from "./LoadingIndicator.jsx";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatWindow({ messages, loading, lite, onRetry }) {
  const endRef = useRef(null);
  const lastMessageRef = useRef(null);
  const lastRole = messages[messages.length - 1]?.role;

  // A new answer opens at its first line, so people aren't dropped at the sources below it.
  useEffect(() => {
    if (!loading && lastRole && lastRole !== "user") lastMessageRef.current?.scrollIntoView({ block: "start" });
    else endRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, loading, lastRole]);

  return (
    <div role="log" aria-live="polite" aria-label="Conversation" className="space-y-5">
      {messages.map((message, index) => (
        <div key={message.id} ref={index === messages.length - 1 ? lastMessageRef : null} className="scroll-mt-20">
          <MessageBubble
            message={message}
            lite={lite}
            onRetry={message.role === "error" && index === messages.length - 1 ? onRetry : undefined}
          />
        </div>
      ))}
      {loading && <LoadingIndicator />}
      <div ref={endRef} />
    </div>
  );
}
