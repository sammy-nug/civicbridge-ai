import { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { Menu, X, Zap } from "lucide-react";
import Logo from "./Logo.jsx";

const LINKS = [
  { to: "/chat", label: "Ask" },
  { to: "/verify", label: "Check information" },
  { to: "/resources", label: "Resources" },
  { to: "/about", label: "About" },
];

export default function Navbar({ lite, onToggleLite }) {
  const [open, setOpen] = useState(false);
  const linkClass = ({ isActive }) =>
    `block rounded-md px-3 py-2 font-medium ${isActive ? "bg-blue-50 text-blue-800" : "text-navy hover:bg-slate-100"}`;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2 sm:px-6">
        <Link to="/" aria-label="CivicBridge AI home" className="min-h-[44px] content-center" onClick={() => setOpen(false)}>
          <Logo />
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass}>{link.label}</NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onToggleLite}
            aria-pressed={lite}
            className={`inline-flex min-h-[44px] items-center gap-1.5 rounded-md border px-2.5 text-sm font-medium ${lite ? "border-green-800 bg-green-50 text-green-900" : "border-slate-300 text-navy hover:bg-slate-100"}`}
          >
            <Zap aria-hidden="true" size={16} />
            <span>Data saver{lite ? ": on" : ""}</span>
          </button>
          <button
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-md hover:bg-slate-100 md:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen(!open)}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-menu" aria-label="Mobile" className="border-t border-slate-200 px-4 py-2 md:hidden">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass} onClick={() => setOpen(false)}>{link.label}</NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
