import { useEffect, useRef, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import Footer from "./components/Footer.jsx";
import Navbar from "./components/Navbar.jsx";
import About from "./pages/About.jsx";
import Chat from "./pages/Chat.jsx";
import Home from "./pages/Home.jsx";
import Resources from "./pages/Resources.jsx";
import Verify from "./pages/Verify.jsx";

function readStored(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback; // Storage can be blocked; the app should still work.
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Preferences just won't persist. */
  }
}

function initialLite() {
  const stored = readStored("civicbridge-lite", null);
  if (stored !== null) return stored === "true";
  return Boolean(navigator.connection?.saveData); // Respect the browser's data-saver setting.
}

const PAGE_TITLES = {
  "/": "CivicBridge AI: Nigerian election information from official sources",
  "/chat": "Ask CivicBridge | CivicBridge AI",
  "/verify": "Check Electoral Information | CivicBridge AI",
  "/resources": "Official electoral documents | CivicBridge AI",
  "/about": "About | CivicBridge AI",
};

// A page change in a single-page app is silent to screen readers unless the title and focus move too.
function PageChangeEffects() {
  const { pathname } = useLocation();
  const previous = useRef(pathname);
  useEffect(() => {
    document.title = PAGE_TITLES[pathname] || "Page not found | CivicBridge AI";
    if (previous.current === pathname) return;
    previous.current = pathname;
    window.scrollTo(0, 0);
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [pathname]);
  return null;
}

function NotFound() {
  return (
    <div className="page">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <Link to="/" className="text-link mt-3 inline-block">Go to the home page</Link>
    </div>
  );
}

// The chat page works like an app: its message box sits at the bottom of the screen, not above a footer.
function SiteFooter() {
  return useLocation().pathname === "/chat" ? null : <Footer />;
}

export default function App() {
  const [language, setLanguage] = useState(() => {
    const stored = readStored("civicbridge-language", "en");
    return ["en", "ha", "yo", "ig"].includes(stored) ? stored : "en";
  });
  const [lite, setLite] = useState(initialLite);
  const [chat, setChat] = useState({ sessionId: null, messages: [] });

  useEffect(() => writeStored("civicbridge-language", language), [language]);
  useEffect(() => {
    writeStored("civicbridge-lite", String(lite));
    document.documentElement.dataset.lite = String(lite);
  }, [lite]);

  return (
    <BrowserRouter>
      <PageChangeEffects />
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-30 focus:rounded focus:bg-white focus:p-2">Skip to main content</a>
      <div className="flex min-h-dvh flex-col">
        <Navbar lite={lite} onToggleLite={() => setLite(!lite)} />
        <main id="main" tabIndex={-1} className="flex flex-1 flex-col">
          <Routes>
            <Route path="/" element={<Home language={language} setLanguage={setLanguage} lite={lite} />} />
            <Route path="/chat" element={<Chat chat={chat} setChat={setChat} language={language} setLanguage={setLanguage} lite={lite} />} />
            <Route path="/verify" element={<Verify language={language} setLanguage={setLanguage} lite={lite} />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <SiteFooter />
      </div>
    </BrowserRouter>
  );
}
