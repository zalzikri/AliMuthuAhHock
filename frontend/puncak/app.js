const $ = (selector) => document.querySelector(selector);
const STORAGE_KEY = "puncak.player";
const SVG_NS = "http://www.w3.org/2000/svg";
const WORLD_W = 600;
const WORLD_H = 2400;
const CLIMB_MS = 1500;

let player = "";
let daily = null;
let current = 0;
let deadline = 0;
let ticking = null;
let busy = false;

// The score is altitude on the mountain trail: 0 points is the gate, 80% of the maximum is the peak.
const BASE = 1866;
const SUMMIT = 4095;
const CHECKPOINTS = [
  { alt: 1866, name: "Timpohon Gate" },
  { alt: 1981, name: "Kandis Shelter" },
  { alt: 2515, name: "Mempening Shelter" },
  { alt: 2702, name: "Layang-Layang" },
  { alt: 3080, name: "Paka Cave" },
  { alt: 3272, name: "Laban Rata" },
  { alt: 3668, name: "Sayat-Sayat" },
  { alt: 4095, name: "Low's Peak" },
];

const TIERS = [
  { min: 85, tier: 4, label: "Giant stride! Hardly anyone says that.", square: "🟧" },
  { min: 60, tier: 3, label: "Strong step. An uncommon pick.", square: "🟩" },
  { min: 35, tier: 2, label: "Steady. Plenty of people say that.", square: "🟦" },
  { min: 1, tier: 1, label: "Small step. The whole office says that.", square: "⬜" },
  { min: 0, tier: 0, label: "Slipped! No ground gained.", square: "🟥" },
];
const tierFor = (points) => TIERS.find((t) => points >= t.min);

// ---- helpers ---------------------------------------------------------------

function remembered() {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function remember(name) {
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    /* private window: the name just won't be remembered */
  }
}

// Inside Day One the game lives under /puncak and its server calls under /api/puncak.
const API = location.pathname.startsWith("/puncak") ? "/api/puncak" : "/api";

async function api(path, body) {
  const options = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined;
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "Request failed");
  return data;
}

function showError(message) {
  $("#error").textContent = message;
  $("#error").hidden = !message;
}

function show(id) {
  for (const section of ["landing", "play", "done"]) $(`#${section}`).hidden = section !== id;
  window.scrollTo({ top: 0 });
}

function svg(tag, attrs = {}, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (text !== undefined) el.textContent = text;
  return el;
}

/** Animates a number from one value to another and hands each frame to `draw`. */
function countTo(from, to, ms, draw) {
  const startedAt = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - startedAt) / ms);
    draw(Math.round(from + (to - from) * (1 - (1 - t) ** 3)));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function hash(text) {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

const maxScore = () => daily.questions.length * 100;
const totalScore = () => Object.values(daily.progress).reduce((sum, r) => sum + (r.points ?? 0), 0);
// The summit is reached at this score, not at a perfect one.
const summitScore = () => daily.summitScore ?? maxScore();
const climbFraction = (score) => Math.min(1, score / summitScore());
const metres = (points) => Math.round(climbFraction(points) * (SUMMIT - BASE));
const altitudeFor = (score) => BASE + metres(score);
const checkpointFor = (altitude) => [...CHECKPOINTS].reverse().find((cp) => altitude >= cp.alt);
const fmt = (n) => n.toLocaleString("en-US");

// ---- the mountain ----------------------------------------------------------

let shownFraction = 0;
let shownAltitude = BASE;
let climbFrame = null;
// Add ?preview=0.8 to the address to look at the mountain from 80% of the way up (for demos and checks).
const previewParam = new URLSearchParams(location.search).get("preview");
const previewFraction = previewParam === null ? null : Number(previewParam);
let mountain3d = null; // set once the 3D model has loaded; until then (or if it fails) the drawn mountain shows
let lastClimbers = [];

// The drawn mountain is the default. To use a 3D model instead, put a .glb file in public/assets/
// and set its path here, for example "assets/mountain.glb".
const MODEL_3D = "assets/mountain_1.glb";

async function start3d() {
  if (!MODEL_3D) return;
  // Hide the drawn mountain while the 3D one loads, so it does not flash up first.
  $(".world").classList.add("loading-3d");
  $("#world-loading").hidden = false;
  try {
    const { initMountain3D } = await import("./mountain3d.js");
    mountain3d = await initMountain3D({
      modelUrl: MODEL_3D,
      container: $(".world"),
      checkpoints: CHECKPOINTS.map((cp) => ({
        name: cp.name,
        label: `${fmt(cp.alt)} m`,
        fraction: (cp.alt - BASE) / (SUMMIT - BASE),
      })),
      // The Kopi easter egg: a tiny coffee stall by the trail at Laban Rata, the rest house on the real climb.
      kopi: { modelUrl: "assets/coffee_shop.glb", fraction: 0.63, onFound: kopiMoment },
    });
    $(".world").classList.add("is-3d");
    if (daily) {
      mountain3d.setProgress(previewFraction ?? climbFraction(totalScore()), { instant: true });
      pushOthersTo3d();
    }
    // Add &celebrate=1 to the address (with ?preview=) to replay the finale from that height, for demos and checks.
    if (new URLSearchParams(location.search).has("celebrate")) {
      finale(BASE + Math.round((previewFraction ?? 0) * (SUMMIT - BASE)));
    }
  } catch (err) {
    console.warn("3D mountain unavailable, using the drawn one:", err);
  } finally {
    $(".world").classList.remove("loading-3d");
    $("#world-loading").hidden = true;
    if (daily) updateCamera(climbFraction(totalScore()));
  }
}

function pushOthersTo3d() {
  if (!mountain3d || !daily) return;
  mountain3d.setOthers(
    lastClimbers.map((climber) => {
      const key = climber.name.toLowerCase();
      const h = hash(key);
      return {
        key,
        initials: climber.name.split(/\s+/).slice(0, 2).map((word) => word[0]?.toUpperCase() ?? "").join(""),
        color: `hsl(${h % 360} 75% 68%)`,
        nudge: ((h >> 8) % 25) - 12,
        title: `${climber.name} · ${fmt(altitudeFor(climber.score))} m · ${climber.answered} of ${daily.questions.length} answered`,
        fraction: climbFraction(climber.score),
      };
    }),
  );
}

/** A point on the trail in scene units: 0 = gate, 1 = summit. */
function trailPoint(fraction) {
  const trail = $("#trail");
  return trail.getPointAtLength(Math.max(0, Math.min(1, fraction)) * trail.getTotalLength());
}

function buildScene() {
  // Checkpoints along the trail, labelled on whichever side has room.
  $("#checkpoints").replaceChildren(
    ...CHECKPOINTS.map((cp) => {
      const point = trailPoint((cp.alt - BASE) / (SUMMIT - BASE));
      const left = point.x > 300;
      const group = svg("g", { class: "checkpoint", "data-alt": cp.alt });
      const label = svg("text", { x: point.x + (left ? -16 : 16), y: point.y + 2, "text-anchor": left ? "end" : "start" }, cp.name);
      const alt = svg("text", { class: "alt", x: point.x + (left ? -16 : 16), y: point.y + 21, "text-anchor": left ? "end" : "start" }, `${fmt(cp.alt)} m`);
      group.append(svg("circle", { cx: point.x, cy: point.y, r: 7 }), label, alt);
      return group;
    }),
  );

  // Forest on the lower slopes: the same trees every time.
  const left = [[2400, 0], [2150, 0], [2000, 40], [1820, 90], [1640, 130], [1450, 165]];
  const right = [[2400, 600], [2200, 600], [1980, 585], [1680, 560], [1380, 530]];
  const edge = (points, y) => {
    for (let i = 0; i < points.length - 1; i++) {
      const [y1, x1] = points[i];
      const [y2, x2] = points[i + 1];
      if (y <= y1 && y >= y2) return x1 + ((x2 - x1) * (y1 - y)) / (y1 - y2);
    }
    return points.at(-1)[1];
  };
  let seed = 7;
  const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  const trees = [];
  for (let i = 0; i < 150; i++) {
    const y = 1500 + random() * 880;
    const thinning = (y - 1500) / 880; // fewer trees higher up
    if (random() > 0.25 + thinning * 0.75) continue;
    const x = edge(left, y) + 24 + random() * (edge(right, y) - edge(left, y) - 48);
    const size = 10 + random() * 9;
    trees.push(svg("path", { d: `M${x} ${y - size * 2.2} l${-size} ${size * 1.4} h${size * 0.6} l${-size * 0.7} ${size} h${size * 2.2} l${-size * 0.7} ${-size} h${size * 0.6} z` }));
  }
  $("#trees").replaceChildren(...trees);

  // A few cracks in the granite near the top.
  const ridges = ["M318 330 L304 520 L296 760", "M352 240 L372 520 L400 800", "M335 260 L338 470", "M290 900 L262 1180", "M420 900 L452 1190"];
  $("#ridges").replaceChildren(...ridges.map((d) => svg("path", { d })));
}

/** Keeps the climber about 60% of the way down the screen, without showing below the mountain's foot. */
function updateCamera(fraction) {
  const scale = $("#world-svg").clientWidth / WORLD_W;
  if (!scale) return; // the drawn mountain is hidden
  const cam = Math.max(window.innerHeight * 0.6 - trailPoint(fraction).y * scale, window.innerHeight - WORLD_H * scale);
  document.documentElement.style.setProperty("--cam", `${Math.round(cam)}px`);
}

function placeClimber(fraction) {
  const point = trailPoint(fraction);
  $("#climber").setAttribute("transform", `translate(${point.x} ${point.y})`);
  // Keep the label clear of checkpoint names: left of the dot near the gate and on the right-hand bends.
  $("#climber .you").setAttribute("x", point.x > 430 || fraction < 0.03 ? -62 : 20);
}

function toast(message) {
  const box = $("#toast");
  box.hidden = true;
  void box.offsetWidth; // restart the animation
  box.textContent = message;
  box.hidden = false;
}

/** The end of every climb: sunrise floods the sky, the place you reached appears, and the camera circles you. */
function finale(altitude) {
  const atSummit = altitude >= SUMMIT;
  $("#summit-kicker").textContent = atSummit ? "SUNRISE AT THE TOP" : "SUNRISE AT";
  $("#summit-title").textContent = checkpointFor(altitude).name.toUpperCase();
  $("#summit-sub").textContent = `${fmt(altitude)} m${atSummit ? " · a perfect climb" : ""}`;
  const banner = $("#summit");
  banner.hidden = true;
  $("#sunburst").classList.remove("on");
  void banner.offsetWidth; // restart the animations
  banner.hidden = false;
  $("#sunburst").classList.add("on");
  mountain3d?.celebrate({ summit: true });
  setTimeout(() => (banner.hidden = true), 10000);
}

function renderMountain({ announce = false } = {}) {
  const score = totalScore();
  const target = climbFraction(score);
  const altitude = altitudeFor(score);
  document.documentElement.style.setProperty("--fill", String(target));
  updateCamera(target);
  mountain3d?.setProgress(previewFraction ?? target);

  const reached = checkpointFor(altitude);
  $("#level").textContent = reached.name.toUpperCase();
  for (const group of $("#checkpoints").children) {
    group.classList.toggle("reached", altitude >= Number(group.dataset.alt));
  }
  if (announce && reached.alt > BASE && checkpointFor(shownAltitude).alt < reached.alt) {
    toast(`You reached ${reached.name}, ${fmt(reached.alt)} m`);
  }

  countTo(shownAltitude, altitude, CLIMB_MS, (value) => ($("#altitude").textContent = fmt(value)));
  shownAltitude = altitude;

  // Walk the climber up the trail to the new position.
  const from = shownFraction;
  const startedAt = performance.now();
  cancelAnimationFrame(climbFrame);
  const step = (now) => {
    const t = Math.min(1, (now - startedAt) / CLIMB_MS);
    shownFraction = from + (target - from) * (1 - (1 - t) ** 3);
    placeClimber(shownFraction);
    if (t < 1) climbFrame = requestAnimationFrame(step);
  };
  climbFrame = requestAnimationFrame(step);
}

// ---- colleagues on the mountain -------------------------------------------

const otherNodes = new Map();

function renderOthers(climbers) {
  lastClimbers = climbers;
  pushOthersTo3d();
  const seen = new Set();
  for (const climber of climbers) {
    const key = climber.name.toLowerCase();
    seen.add(key);
    let node = otherNodes.get(key);
    if (!node) {
      const h = hash(key);
      const initials = climber.name.split(/\s+/).slice(0, 2).map((word) => word[0]?.toUpperCase() ?? "").join("");
      node = svg("g", { class: "other" });
      node.append(svg("title"), svg("circle", { r: 11, fill: `hsl(${h % 360} 75% 68%)` }), svg("text", { y: 3.5 }, initials));
      node.jitter = { x: ((h >> 8) % 37) - 18, y: ((h >> 16) % 19) - 9 };
      otherNodes.set(key, node);
      $("#others").append(node);
    }
    const point = trailPoint(climbFraction(climber.score));
    node.style.transform = `translate(${point.x + node.jitter.x}px, ${point.y + node.jitter.y}px)`;
    node.querySelector("title").textContent = `${climber.name} · ${fmt(altitudeFor(climber.score))} m · ${climber.answered} of ${daily.questions.length} answered`;
  }
  for (const [key, node] of otherNodes) {
    if (!seen.has(key)) {
      node.remove();
      otherNodes.delete(key);
    }
  }
  const n = climbers.length;
  $("#others-count").textContent = n === 0 ? "" : `${n} colleague${n === 1 ? "" : "s"} on the mountain`;
}

async function refreshOthers() {
  if (!daily) return;
  try {
    const { climbers } = await api(`${API}/climbers?player=${encodeURIComponent(player)}`);
    renderOthers(climbers);
  } catch {
    /* the next refresh will try again */
  }
}

// ---- play ------------------------------------------------------------------

function renderHud(options) {
  $("#dots").replaceChildren(
    ...daily.questions.map((question, i) => {
      const li = document.createElement("li");
      const record = daily.progress[question.id];
      if (record?.done) li.className = `t${tierFor(record.points).tier}`;
      else if (i === current) li.className = "current";
      return li;
    }),
  );
  $("#score").textContent = totalScore();
  $("#max-score").textContent = maxScore();
  renderMountain(options);
}

function stopClock() {
  cancelAnimationFrame(ticking);
  ticking = null;
}

function runClock() {
  const left = Math.max(0, deadline - performance.now());
  $("#clock-fill").style.transform = `scaleX(${left / daily.timeLimitMs})`;
  $("#clock-text").textContent = Math.ceil(left / 1000);
  $("#clock").classList.toggle("low", left < 8000);
  if (left <= 0) {
    stopClock();
    timeUp();
    return;
  }
  ticking = requestAnimationFrame(runClock);
}

function timeUp() {
  if (daily.progress[daily.questions[current].id]?.done) return;
  // An answer may still be in flight; wait for it before closing the question.
  if (busy) setTimeout(timeUp, 150);
  else send({ giveUp: true });
}

function setInputEnabled(enabled) {
  $("#answer").disabled = !enabled;
  $("#submit").disabled = !enabled;
}

async function beginQuestion(index) {
  current = index;
  const question = daily.questions[index];
  $("#order").textContent = `Question ${index + 1} of ${daily.questions.length} · ${question.category}`;
  $("#prompt").textContent = question.prompt;
  $("#kind").textContent =
    question.type === "rarity" ? "RARITY QUESTION · the rarer your answer, the more it scores" : "ANY CORRECT ANSWER SCORES 100";
  $("#blurb").textContent = question.blurb || `${question.answerCount} answers count.`;
  $("#answer").value = "";
  $("#miss").textContent = "";
  $("#result").hidden = true;
  $("#clock").hidden = false;
  $("#answer-form").hidden = false;
  renderHud();
  show("play");

  try {
    const started = await api(`${API}/start`, { player, questionId: question.id });
    deadline = performance.now() + started.remainingMs;
    setInputEnabled(true);
    $("#answer").focus();
    runClock();
  } catch (err) {
    showError(err.message);
  }
}

function factLine(element, lead, name, note) {
  element.replaceChildren();
  element.hidden = !note;
  if (!note) return;
  const strong = document.createElement("b");
  strong.textContent = name;
  element.append(lead, strong, `: ${note}`);
}

function showResult(record) {
  stopClock();
  setInputEnabled(false);
  $("#clock").hidden = true;
  $("#answer-form").hidden = true;
  $("#miss").textContent = "";

  const tier = tierFor(record.points);
  const gained = metres(record.points);
  $("#result").classList.toggle("slipped", !record.answer);
  countTo(0, gained, 900, (value) => ($("#result-points").textContent = `+${fmt(value)} m`));
  const isRarity = record.type === "rarity";
  const RARITY_LABELS = {
    "very rare": "Very rare pick! Giant stride.",
    rare: "Rare pick. Strong step.",
    common: "Common pick. Small step.",
  };
  $("#result-tier").textContent = !record.answer
    ? tier.label
    : isRarity
      ? (RARITY_LABELS[record.tier] ?? tier.label)
      : "Correct! Full stride.";
  const other = record.rarest;
  $("#result-detail").textContent = !record.answer
    ? `${record.answerCount} answers would have counted, such as "${other.text}".`
    : !isRarity
      ? `+${record.points} points for "${record.answer}".`
      : record.points >= 100
        ? `+${record.points} points. "${record.answer}" is a very rare answer.`
        : `+${record.points} points for "${record.answer}", a ${record.tier} answer. "${other.text}" would have scored +${other.points}.`;

  // What the player can learn from this question: their own answer, and one they did not give.
  const rarestIsTheirs = record.answer === other.text;
  factLine($("#fact-yours"), "", record.answer ?? "", record.answer ? record.note : null);
  factLine($("#fact-rarest"), isRarity ? "A rarer answer, " : "Another answer, ", other.text, rarestIsTheirs ? null : other.note);
  $("#fact").hidden = $("#fact-yours").hidden && $("#fact-rarest").hidden;

  const last = daily.questions.every((question) => daily.progress[question.id]?.done);
  $("#next").textContent = last ? "SEE TODAY'S CLIMB" : "KEEP CLIMBING";
  $("#result").hidden = false;
  $("#next").focus();
  renderHud({ announce: true });
  refreshOthers();
}

async function send({ answer = "", giveUp = false } = {}) {
  if (busy) return;
  busy = true;
  showError("");
  try {
    const question = daily.questions[current];
    const record = await api(`${API}/answer`, { player, questionId: question.id, answer, giveUp });
    if (record.done) {
      daily.progress[question.id] = record;
      showResult(record);
    } else if (record.suggestion) {
      // Close, but not exact: offer the answer it looks like. Clicking it (or typing it) answers with it.
      const offer = Object.assign(document.createElement("button"), {
        type: "button",
        className: "link suggest",
        textContent: `"${record.suggestion}"`,
      });
      offer.addEventListener("click", () => send({ answer: record.suggestion }));
      $("#miss").replaceChildren("Did you mean ", offer, "?");
      $("#answer").focus();
    } else {
      const form = $("#answer-form");
      form.classList.remove("shake");
      void form.offsetWidth; // restart the animation
      form.classList.add("shake");
      $("#miss").textContent = `"${answer}" is not a valid answer. Try another.`;
      // Only clear the box if the player has not already started typing their next guess.
      if ($("#answer").value.trim() === answer) $("#answer").value = "";
      $("#answer").focus();
    }
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
  }
}

function next() {
  const upcoming = daily.questions.findIndex((question) => !daily.progress[question.id]?.done);
  if (upcoming === -1) showResults();
  else beginQuestion(upcoming);
}

// ---- results ---------------------------------------------------------------

function renderBreakdown(results) {
  $("#breakdown").replaceChildren(
    ...results.questions.map((question) => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = question.prompt;
      const yours = document.createElement("small");
      yours.textContent = question.yours.answer ? `You: ${question.yours.answer} (+${question.yours.points})` : "You: slipped (+0)";
      summary.append(yours);

      const list = document.createElement("ul");
      list.className = "answers";
      for (const answer of question.answers) {
        const li = document.createElement("li");
        if (answer.text === question.yours.answer) li.className = "mine";
        const name = document.createElement("span");
        name.textContent = answer.text;
        const bar = document.createElement("span");
        bar.className = "bar";
        const fill = document.createElement("i");
        fill.style.width = `${answer.points}%`;
        bar.append(fill);
        const points = document.createElement("span");
        points.className = "pts";
        points.textContent = answer.points;
        li.append(name, bar, points);
        if (answer.note) {
          const note = document.createElement("span");
          note.className = "note";
          note.textContent = answer.note;
          li.append(note);
        }
        list.append(li);
      }
      details.append(summary, list);
      return details;
    }),
  );
}

function renderLeaderboard(rows) {
  $("#leaderboard").replaceChildren(
    ...rows.map((row) => {
      const li = document.createElement("li");
      if (row.name.toLowerCase() === player.toLowerCase()) li.className = "me";
      const score = document.createElement("span");
      score.textContent = `${fmt(altitudeFor(row.score))} m`;
      li.append(row.name, score);
      return li;
    }),
  );
}

async function showResults() {
  showError("");
  try {
    const results = await api(`${API}/results?player=${encodeURIComponent(player)}`);
    const total = results.questions.reduce((sum, q) => sum + q.yours.points, 0);
    const squares = results.questions.map((q) => tierFor(q.yours.points).square).join("");
    const altitude = altitudeFor(total);
    const reached = checkpointFor(altitude).name;
    const level = altitude >= SUMMIT ? "Summit! Low's Peak" : reached;

    $("#final-level").textContent = level.toUpperCase();
    $("#final-altitude").textContent = `${fmt(altitude)} m`;
    $("#final-score").textContent = total;
    $("#final-max").textContent = maxScore();
    $("#grid").textContent = squares;
    renderLeaderboard(results.leaderboard);
    renderBreakdown(results);
    renderMountain();

    $("#share").onclick = async () => {
      const text = `Puncak #${results.number}\n${fmt(altitude)} m · ${reached} · ${total}/${maxScore()}\n${squares}`;
      try {
        await navigator.clipboard.writeText(text);
        $("#share").textContent = "COPIED";
      } catch {
        $("#share").textContent = "COPY NOT AVAILABLE HERE";
      }
    };
    show("done");
    finale(altitude);
  } catch (err) {
    showError(err.message);
  }
}

// ---- the Kopi easter egg -----------------------------------------------------

let kopiTimer;
function kopiMoment() {
  const banner = $("#summit");
  $("#summit-kicker").textContent = "HERE'S AN EASTER EGG";
  $("#summit-title").textContent = "KOPI BREAK ☕";
  $("#summit-sub").textContent = "Thank you to everyone who organised KopiCode.";
  // Restart the banner's fade-in even if it is already showing.
  banner.hidden = true;
  void banner.offsetWidth;
  banner.hidden = false;
  clearTimeout(kopiTimer);
  kopiTimer = setTimeout(() => (banner.hidden = true), 10000);
}

// ---- start -----------------------------------------------------------------

async function loadDaily(name) {
  daily = await api(`${API}/daily?player=${encodeURIComponent(name)}`);
  renderMountain();
}

async function boot() {
  buildScene();
  start3d();
  // A link can carry the player's name (?name=Aina), as the Day One page does.
  const saved = new URLSearchParams(location.search).get("name")?.trim().slice(0, 24) || remembered();
  try {
    player = saved;
    await loadDaily(saved);
    $("#player").value = saved;
    $("#foot").textContent = `Climb #${daily.number} · ${daily.date} · ${daily.company}`;
    const started = Object.keys(daily.progress).length > 0;
    $("#begin").textContent = started ? "CONTINUE THE CLIMB" : "START THE CLIMB";
    show("landing");
    $("#player").focus();
    refreshOthers();
    setInterval(refreshOthers, 8000);
  } catch (err) {
    show("landing");
    showError(err.message);
  }
}

$("#join-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = $("#player").value.trim();
  if (!name) return;
  showError("");
  try {
    player = name;
    remember(name);
    await loadDaily(name);
    refreshOthers();
    next();
  } catch (err) {
    showError(err.message);
  }
});

$("#answer-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const answer = $("#answer").value.trim();
  if (answer) send({ answer });
});

$("#next").addEventListener("click", next);
$("#open-how").addEventListener("click", () => $("#how").showModal());
$("#open-works").addEventListener("click", () => $("#works").showModal());
window.addEventListener("resize", () => daily && updateCamera(climbFraction(totalScore())));

boot();
