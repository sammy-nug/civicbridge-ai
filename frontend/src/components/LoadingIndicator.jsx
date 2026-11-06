import { useEffect, useState } from "react";

// Slow networks and models are expected, so after a while we say so rather than look frozen.
export default function LoadingIndicator({ label = "Searching official sources" }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div role="status" className="flex flex-wrap items-center gap-2 text-slate-700">
      <span aria-hidden="true" className="flex gap-1">
        <span className="dot h-2 w-2 rounded-full bg-civic-blue" />
        <span className="dot h-2 w-2 rounded-full bg-civic-blue" />
        <span className="dot h-2 w-2 rounded-full bg-civic-blue" />
      </span>
      <span>{label}…</span>
      {slow && <span className="text-sm">Still working. This can take a little longer on slow connections.</span>}
    </div>
  );
}
