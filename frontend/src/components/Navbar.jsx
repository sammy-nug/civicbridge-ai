import { useEffect, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { Menu, X, Zap } from "lucide-react";
import Logo from "./Logo.jsx";

const LINKS = [
  { to: "/chat", label: "Ask" },
  { to: "/verify", label: "Check information" },
  { to: "/resources", label: "Resources" },
  { to: "/about", label: "About" },
];

function DataSaverButton({ lite, onToggle, className = "" }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={lite}
      className={`min-h-[44px] items-center gap-1.5 rounded border px-2.5 text-sm font-medium ${lite ? "border-civic-green bg-civic-tint text-civic-greenDark" : "border-rule text-ink hover:bg-paper"} ${className}`}
    >
      <Zap aria-hidden="true" size={16} />
      <span>Data saver{lite ? ": on" : ""}</span>
    </button>
  );
}

export default function Navbar({ lite, onToggleLite }) {
  const [open, setOpen] = useState(false);
  const menuButton = useRef(null);
  const linkClass = ({ isActive }) =>
    `block border-b-2 px-3 py-2 font-medium ${isActive ? "border-civic-green text-civic-greenDark" : "border-transparent text-ink hover:border-rule"}`;

  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <>
      {/* Always stated first: this must never be mistaken for INEC or a government site. */}
      <section aria-label="About this website" className="bg-ink px-4 py-1.5 text-center text-xs text-white sm:px-6 sm:text-sm">
        Independent project. Not INEC or a government website.
      </section>
      <header className="sticky top-0 z-20 border-b border-rule bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-1.5 sm:px-6">
          <Link to="/" aria-label="CivicBridge AI home" className="min-h-[44px] content-center" onClick={() => setOpen(false)}>
            <Logo />
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className={linkClass}>{link.label}</NavLink>
            ))}
          </nav>
          <DataSaverButton lite={lite} onToggle={onToggleLite} className="hidden md:inline-flex" />
          <button
            ref={menuButton}
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded hover:bg-paper md:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen(!open)}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
        {open && (
          <nav id="mobile-menu" aria-label="Mobile" className="border-t border-rule px-4 py-2 md:hidden">
            {LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className={linkClass} onClick={() => setOpen(false)}>{link.label}</NavLink>
            ))}
            <DataSaverButton lite={lite} onToggle={onToggleLite} className="mt-2 inline-flex" />
          </nav>
        )}
      </header>
    </>
  );
}
