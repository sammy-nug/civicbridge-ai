import { useEffect, useRef } from "react";
import LoadingIndicator from "./LoadingIndicator.jsx";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatWindow({ messages, loading, lite, onRetry }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, loading]);

  return (
    <div role="log" aria-live="polite" aria-label="Conversation" className="space-y-5">
      {messages.map((message, index) => (
        <MessageBubble
          key={message.id}
          message={message}
          lite={lite}
          onRetry={message.role === "error" && index === messages.length - 1 ? onRetry : undefined}
        />
      ))}
      {loading && <LoadingIndicator />}
      <div ref={endRef} />
    </div>
  );
}
