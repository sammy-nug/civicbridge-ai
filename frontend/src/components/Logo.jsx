export default function Logo({ light = false }) {
  return (
    <span className="inline-flex items-center gap-2 font-bold">
      <svg aria-hidden="true" width="30" height="30" viewBox="0 0 32 32">
        <rect width="32" height="32" rx="7" fill={light ? "#FFFFFF" : "#102A43"} />
        <path d="M5 22c4-9 18-9 22 0" fill="none" stroke={light ? "#102A43" : "#FFFFFF"} strokeWidth="3" strokeLinecap="round" />
        <path d="M11 18v5M16 16.500v6.500M21 18v5" stroke={light ? "#15803D" : "#4ADE80"} strokeWidth="2.500" strokeLinecap="round" />
      </svg>
      <span className={`text-lg tracking-tight ${light ? "text-white" : "text-navy"}`}>
        CivicBridge <span className={light ? "text-green-300" : "text-green-800"}>AI</span>
      </span>
    </span>
  );
}
