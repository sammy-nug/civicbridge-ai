import { Link } from "react-router-dom";
import Logo from "./Logo.jsx";

const OFFICIAL_LINKS = [
  { href: "https://www.inecnigeria.org/", label: "INEC official website" },
  { href: "https://cvr.inecnigeria.org/", label: "INEC voter registration portal" },
  { href: "https://www.inecnigeria.org/elections/guidelines", label: "INEC regulations and guidelines" },
  { href: "https://www.inecnigeria.org/voters/education", label: "INEC voter education" },
];

export default function Footer() {
  return (
    <footer className="on-dark mt-auto bg-navy text-slate-100">
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:grid-cols-3 sm:px-6">
        <div className="sm:col-span-1">
          <Logo light />
          <p className="mt-3 text-sm">
            An independent civic education project. Not affiliated with, or speaking for, INEC or any political party.
          </p>
        </div>
        <div>
          <h2 className="font-semibold text-white">Official resources</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {OFFICIAL_LINKS.map((link) => (
              <li key={link.href}>
                <a className="underline hover:text-white" href={link.href} target="_blank" rel="noreferrer">{link.label}</a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold text-white">CivicBridge AI</h2>
          <ul className="mt-2 space-y-2 text-sm">
            <li><Link className="underline hover:text-white" to="/about">How it works and privacy</Link></li>
            <li><Link className="underline hover:text-white" to="/resources">Documents we use</Link></li>
          </ul>
          <p className="mt-3 text-sm">AI can make mistakes. Check important details with INEC.</p>
        </div>
      </div>
    </footer>
  );
}
