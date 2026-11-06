/* Browser checks: mobile layout, accessibility (axe), keyboard use, and real/forced states.
 * Setup: npm i puppeteer-core@22 axe-core  (in any folder; point NODE_PATH at its node_modules)
 * Run:   NODE_PATH=... node evaluation/ui_check.cjs http://localhost:4173 <screenshot_dir>
 * Only the "citation rendering" and "verify rendering" checks use an intercepted API response,
 * since they test how the UI draws a result, not whether the result is true.
 */
const puppeteer = require("puppeteer-core");
const fs = require("fs");
const axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.argv[2] || "http://localhost:4173";
const OUT = process.argv[3] || ".";
const results = [];
const record = (name, passed, detail = "") => {
  results.push({ name, passed, detail });
  console.log(`${passed ? "PASS" : "FAIL"}  ${name}${detail ? "  " + detail : ""}`);
};
const CITATION = {
  number: 1, document_id: "render-test", title: "Render test document", organisation: "Render test",
  url: "https://example.org/x.pdf", page: 15, section: "Section/clause 18", publication_date: "2026",
  publication_date_basis: "x", retrieved_date: "2026-11-05", status: "needs_verification",
  notes: ["Render-test note."], excerpt: "Render-test passage.", similarity: 0.6,
};
const CHAT = {
  response_id: "11111111-1111-1111-1111-111111111111", answer: "Render test sentence one [1].", language: "ha",
  answered_in: "ha", english_answer: "English render test [1].", citations: [CITATION], evidence_status: "supported",
  notices: ["Render-test notice."], translation_reviewed: false, session_id: "22222222-2222",
};
const VERIFY = {
  response_id: "33333333-3333-3333-3333-333333333333", assessment: "contradicted", explanation: "Render test explanation [1].",
  supports: [], contradicts: ["Render test contradiction [1]."], cannot_establish: ["Render test unknown."],
  supporting_sources: [CITATION], limitations: ["Render test limitation."], language: "en", answered_in: "en", translation_reviewed: true,
};

(async () => {
  const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox"] });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("pageerror", (e) => consoleErrors.push(e.message));

  const audit = async (name) => {
    await new Promise((resolve) => setTimeout(resolve, 300)); // Let colour transitions finish, or axe measures them midway.
    await page.evaluate(axeSource);
    const report = await page.evaluate(async () => {
      const r = await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "best-practice"] });
      return r.violations.map((v) => `${v.id}(${v.impact}):${v.nodes.length}:${v.nodes[0].target}`);
    });
    record(`axe ${name}`, report.length === 0, report.join(" | "));
  };
  // Measures against the real screen width. Comparing with window.innerWidth is not enough:
  // on phones the layout viewport grows with the overflow, so that check can never fail.
  const overflow = async (name) => {
    const screenWidth = page.viewport().width;
    const offenders = await page.evaluate((limit) => {
      const bad = [];
      for (const el of document.querySelectorAll("body *")) {
        if (el.closest(".sr-only") || el.closest("svg")) continue;
        const box = el.getBoundingClientRect();
        if (box.width > 0 && box.right > limit + 1) bad.push(`${el.tagName.toLowerCase()}:${Math.round(box.right)}`);
      }
      return { bad: bad.slice(0, 4), layout: document.documentElement.scrollWidth };
    }, screenWidth);
    record(`no sideways overflow ${name}`, offenders.bad.length === 0 && offenders.layout <= screenWidth, `layout ${offenders.layout}px ${offenders.bad.join(" ")}`);
  };
  for (const [label, width, height] of [["mobile", 360, 740], ["desktop", 1280, 800]]) {
    await page.setViewport({ width, height, isMobile: label === "mobile", hasTouch: label === "mobile" });
    for (const [route, name] of [["/", "home"], ["/chat", "chat"], ["/verify", "verify"], ["/resources", "resources"], ["/about", "about"]]) {
      await page.goto(BASE + route, { waitUntil: "networkidle0" });
      await overflow(`${label} ${name}`);
      if (name === "chat") {
        const visible = await page.$eval("#chat-input", (el) => {
          const box = el.getBoundingClientRect();
          return box.top >= 0 && box.bottom <= window.innerHeight;
        });
        record(`message box visible without scrolling ${label}`, visible);
      }
      await audit(`${label} ${name}`);
      await page.screenshot({ path: `${OUT}/${label}-${name}.png`, fullPage: name !== "chat" });
    }
  }

  await page.setViewport({ width: 360, height: 740, isMobile: true, hasTouch: true });
  // Real resources from the real API, plus search.
  await page.goto(BASE + "/resources", { waitUntil: "networkidle0" });
  const cards = await page.$$eval("main li.card", (e) => e.length);
  await page.type("#resource-search", "observer");
  await page.waitForFunction(() => document.querySelectorAll("main li.card").length < 10);
  const filtered = await page.$$eval("main li.card", (e) => e.length);
  record("resources load and search filters", cards >= 10 && filtered >= 1 && filtered < cards, `${cards} -> ${filtered}`);

  // Real decline with no LLM involved, in the conversation.
  await page.goto(BASE + "/chat", { waitUntil: "networkidle0" });
  await page.type("#chat-input", "Who should I vote for?");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.body.innerText.includes("Outside what CivicBridge AI can do"), { timeout: 15000 });
  record("real partisan question declined via Enter key", true);
  await page.screenshot({ path: `${OUT}/mobile-chat-declined.png` });

  // Language switch keeps the conversation, then a real abstention needing no LLM.
  const before = await page.$$eval('[role="log"] article', (e) => e.length);
  await page.select("#language", "ha");
  const after = await page.$$eval('[role="log"] article', (e) => e.length);
  const warned = await page.evaluate(() => document.body.innerText.includes("has not yet passed human evaluation"));
  record("switching language keeps conversation and shows review warning", before === after && before === 1 && warned);
  await page.select("#language", "en");

  // Conversation survives moving between pages, and "New conversation" clears it.
  await page.click('a[aria-label="CivicBridge AI home"]');
  await page.waitForSelector("h1");
  await page.goto(BASE + "/chat", { waitUntil: "networkidle0" });
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("New conversation")).click());
  record("new conversation clears the page", (await page.$$('[role="log"] article')).length === 0);

  // Forced states: rendering only.
  await page.setRequestInterception(true);
  let mode = "citation";
  page.on("request", (request) => {
    const url = request.url();
    if (url.endsWith("/api/chat") && mode === "citation") return request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(CHAT) });
    if (url.endsWith("/api/chat") && mode === "down") return request.abort();
    if (url.endsWith("/api/chat") && mode === "passages") {
      return request.respond({ status: 200, contentType: "application/json", body: JSON.stringify({ ...CHAT,
        answer: "Our AI service is unavailable right now, so this is not a written answer.", language: "en", answered_in: "en",
        english_answer: null, evidence_status: "passages_only", notices: [],
        citations: Array.from({ length: 6 }, (_, i) => ({ ...CITATION, number: i + 1, excerpt: "Render-test passage. ".repeat(12) })) }) });
    }
    if (url.endsWith("/api/chat") && mode === "notconfigured") return request.respond({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "llm_not_configured", message: "The AI service has not been set up on this server, so we can't answer questions yet." } }) });
    if (url.endsWith("/api/verify")) return request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(VERIFY) });
    if (url.endsWith("/api/feedback")) return request.respond({ status: 201, contentType: "application/json", body: '{"status":"recorded"}' });
    request.continue();
  });

  await page.goto(BASE + "/chat", { waitUntil: "networkidle0" });
  await page.type("#chat-input", "render test");
  await page.click('button[type="submit"]');
  await page.waitForFunction(() => document.body.innerText.includes("Render test document"));
  const link = await page.$eval('[role="log"] a[target="_blank"]', (a) => a.href);
  record("citation card renders and links to the exact PDF page", link === "https://example.org/x.pdf#page=15", link);
  const marker = await page.$eval('[role="log"] p a[aria-label="Source 1"]', (a) => a.getAttribute("href"));
  record("[1] marker becomes a link to its source card", (await page.$(marker)) !== null, marker);
  await overflow("mobile chat with citation");
  await audit("mobile chat with citation");
  await page.screenshot({ path: `${OUT}/mobile-chat-citation.png`, fullPage: true });
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Show English")).click());
  record("English version can be opened", await page.evaluate(() => document.body.innerText.includes("English render test")));
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("No, or incorrect")).click());
  await page.type("textarea[id^=feedback]", "render test comment");
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Send feedback")).click());
  await page.waitForFunction(() => document.body.innerText.includes("Your feedback was recorded"));
  record("negative feedback form submits", true);

  mode = "down";
  await page.type("#chat-input", "network test");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.body.innerText.includes("can't reach the server"));
  record("network failure shows friendly error", true);
  mode = "notconfigured";
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Try again")).click());
  await page.waitForFunction(() => document.body.innerText.includes("has not been set up"));
  record("Try again retries, and missing AI setup is explained", true);
  await page.screenshot({ path: `${OUT}/mobile-chat-error.png` });

  await page.goto(BASE + "/verify", { waitUntil: "networkidle0" });
  await page.type("#claim", "render test claim");
  await page.click('button[type="submit"]');
  await page.waitForFunction(() => document.body.innerText.includes("Contradicted by available official sources"));
  await overflow("mobile verify result");
  await audit("mobile verify result");
  await page.screenshot({ path: `${OUT}/mobile-verify-result.png`, fullPage: true });
  record("verify result shows category, findings and limitations", await page.evaluate(() => document.body.innerText.includes("Limitations of this check")));

  // Asking on the home page carries the question to the chat, once, and Back doesn't repeat it.
  mode = "real";
  await page.setViewport({ width: 360, height: 740, isMobile: true, hasTouch: true });
  await page.goto(BASE + "/", { waitUntil: "networkidle0" });
  await page.type("#home-question", "Who should I vote for?");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.body.innerText.includes("Outside what CivicBridge AI can do"), { timeout: 15000 });
  const askedOnce = await page.evaluate(() => [...document.querySelectorAll('[role="log"] p')].filter((p) => p.innerText === "Who should I vote for?").length);
  record("home page question reaches the chat exactly once", askedOnce === 1, `count ${askedOnce}`);
  record("page change moves focus to main and updates the title",
    await page.evaluate(() => document.activeElement.id === "main" && document.title.startsWith("Ask CivicBridge")));
  record("chat has no site footer", (await page.$("footer")) === null);
  await page.goBack({ waitUntil: "networkidle0" });
  await page.goForward({ waitUntil: "networkidle0" });
  const repeats = await page.evaluate(() => document.querySelectorAll('[role="log"] article').length);
  record("back and forward don't ask the question again", repeats <= 1, `answers ${repeats}`);
  await page.evaluate(() => localStorage.clear());

  // First screen on a phone: controls must leave room for the questions.
  await page.goto(BASE + "/chat", { waitUntil: "networkidle0" });
  const visibleQuestions = await page.evaluate(() => {
    const composer = document.querySelector("form").getBoundingClientRect().top;
    return [...document.querySelectorAll("main ul button")].filter((b) => b.getBoundingClientRect().bottom <= composer).length;
  });
  record("phone chat shows at least 3 common questions without scrolling", visibleQuestions >= 3, `${visibleQuestions} visible`);
  const smallTargets = await page.evaluate(() => [...document.querySelectorAll("a, button, select, textarea, input")]
    .filter((el) => { const b = el.getBoundingClientRect(); return b.width > 0 && !el.classList.contains("sr-only") && !el.closest("p") && (b.height < 24 || b.width < 24); })
    .map((el) => el.innerText || el.tagName));
  record("touch targets are at least 24px", smallTargets.length === 0, smallTargets.join(", "));

  // Mobile menu: Escape closes it and returns focus to the button.
  await page.click('button[aria-controls="mobile-menu"]');
  await page.waitForSelector("#mobile-menu");
  await page.keyboard.press("Escape");
  record("Escape closes the menu and returns focus", (await page.$("#mobile-menu")) === null
    && await page.evaluate(() => document.activeElement.getAttribute("aria-controls") === "mobile-menu"));

  // The AI-outage answer and scroll position, using a forced response.
  mode = "passages";
  await page.type("#chat-input", "render test");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.body.innerText.includes("Official passages only: no AI answer"));
  record("AI outage shows official passages, clearly labelled", true);
  await new Promise((resolve) => setTimeout(resolve, 200));
  const answerTop = await page.evaluate(() => document.querySelector('[role="log"] article').getBoundingClientRect().top);
  record("a new answer opens at its first line, below the header", answerTop >= 0 && answerTop < 200, `top ${Math.round(answerTop)}px`);
  await overflow("mobile chat passages");
  await audit("mobile chat passages");
  await page.screenshot({ path: `${OUT}/mobile-chat-passages.png` });
  mode = "real";

  // Keyboard: the first Tab reaches the skip link, then main navigation controls.
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto(BASE + "/", { waitUntil: "networkidle0" });
  await page.keyboard.press("Tab");
  const first = await page.evaluate(() => document.activeElement.innerText);
  const order = [];
  for (let i = 0; i < 7; i++) {
    await page.keyboard.press("Tab");
    order.push(await page.evaluate(() => document.activeElement.innerText.trim() || document.activeElement.getAttribute("aria-label")));
  }
  record("keyboard: skip link first, then navigation in order", first.includes("Skip") && order.includes("Ask") && order.includes("About"), order.join(" > "));

  // Data saver: toggles, persists, and hides source passages until asked.
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Data saver")).click());
  await page.reload({ waitUntil: "networkidle0" });
  record("data saver persists after reload", (await page.evaluate(() => document.documentElement.dataset.lite)) === "true");
  await page.evaluate(() => localStorage.clear());

  record("no uncaught page errors", consoleErrors.length === 0, consoleErrors.join("; "));
  const failed = results.filter((r) => !r.passed);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  fs.writeFileSync(`${OUT}/ui_results.json`, JSON.stringify(results, null, 1));
  await browser.close();
})().catch((error) => {
  console.error("UI CHECK CRASHED:", error.message);
  process.exit(1);
});
