const appShell = document.getElementById("app-shell");
const readingForm = document.getElementById("reading-form");
const chatForm = document.getElementById("chat-form");
const newReadingButton = document.getElementById("new-reading-button");
const intakeScreen = document.getElementById("intake-screen");
const resultScreen = document.getElementById("result-screen");
const formStatus = document.getElementById("form-status");
const chatStatus = document.getElementById("chat-status");
const followUpQuery = document.getElementById("follow-up-query");
const installAppButton = document.getElementById("install-app-button");

const readingTitle = document.getElementById("reading-title");
const readingIntro = document.getElementById("reading-intro");
const traitsList = document.getElementById("traits-list");
const emotionsList = document.getElementById("emotions-list");
const relationshipsList = document.getElementById("relationships-list");
const careerList = document.getElementById("career-list");
const pastList = document.getElementById("past-list");
const presentList = document.getElementById("present-list");
const futureList = document.getElementById("future-list");
const strengthsList = document.getElementById("strengths-list");
const watchList = document.getElementById("watch-list");
const highlightsList = document.getElementById("highlights-list");
const chatStarters = document.getElementById("chat-starters");
const chatThreadSection = document.getElementById("chat-thread-section");
const chatThread = document.getElementById("chat-thread");
const constellationCanvas = document.getElementById("constellation-canvas");

let latestBirthData = null;
let latestRenderedReading = null;
let chatTranscript = [];
let deferredInstallPrompt = null;

bootImmersiveFrontend();

readingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = buildReadingPayload();
  if (!payload) {
    return;
  }

  setBusy(readingForm, true);
  setStatus(formStatus, "Opening your reading...");

  try {
    const result = await requestPrediction(payload);
    latestBirthData = payload.birth_data;
    latestRenderedReading = result;
    chatTranscript = [];
    renderHumanReading(result);
    renderChatTranscript();
    enterResultMode();
    persistAppState();
    setStatus(formStatus, "Your reading is ready.", true);
  } catch (error) {
    setStatus(formStatus, error.message || "Something went wrong while generating the reading.");
  } finally {
    setBusy(readingForm, false);
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!latestBirthData) {
    setStatus(chatStatus, "Open your reading first.");
    return;
  }

  const query = followUpQuery.value.trim();
  if (!query) {
    setStatus(chatStatus, "Ask a follow-up question first.");
    return;
  }

  setBusy(chatForm, true);
  setStatus(chatStatus, "Updating your reading...");

  try {
    const result = await requestPrediction({
      birth_data: latestBirthData,
      query,
      life_domain: inferLifeDomain(query),
      tradition: "vedic",
      time_horizon: "1year",
      query_type: "general",
      known_facts: [],
    });
    chatTranscript.push({
      role: "user",
      text: query,
    });
    chatTranscript.push({
      role: "assistant",
      text: result.chat_response || composeChatAnswer(result, query),
    });
    renderChatTranscript();
    persistAppState();
    followUpQuery.value = "";
    setStatus(chatStatus, "Added a deeper layer to your reading.", true);
  } catch (error) {
    setStatus(chatStatus, error.message || "Unable to process that question.");
  } finally {
    setBusy(chatForm, false);
  }
});

newReadingButton.addEventListener("click", () => {
  appShell.classList.remove("mode-result");
  intakeScreen.setAttribute("aria-hidden", "false");
  resultScreen.setAttribute("aria-hidden", "true");
  followUpQuery.value = "";
  chatTranscript = [];
  setStatus(chatStatus, "");
  persistAppState();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

async function requestPrediction(payload) {
  const response = await fetch("/api/predict", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await safeJson(response);
    throw new Error(formatError(error?.detail));
  }

  return response.json();
}

function buildReadingPayload() {
  const formData = new FormData(readingForm);
  const fullName = normalizeEmpty(formData.get("full_name"));
  const birthPlace = normalizeEmpty(formData.get("birth_place"));
  const date = normalizeEmpty(formData.get("date"));
  const time = withSeconds(normalizeEmpty(formData.get("time")));

  if (!fullName || !date || !time || !birthPlace) {
    setStatus(formStatus, "Please fill in full name, birth date, birth time, and birth place.");
    return null;
  }

  return {
    birth_data: {
      full_name: fullName,
      date,
      time,
      birth_place: birthPlace,
      time_confidence: "approximate",
    },
    query: normalizeEmpty(formData.get("query")) || "Give me a full personal reading.",
    life_domain: inferLifeDomain(formData.get("query")),
    tradition: "vedic",
    time_horizon: "1year",
    query_type: "general",
    known_facts: [],
  };
}

function renderHumanReading(result) {
  latestRenderedReading = result;
  const reading = result.human_reading || fallbackHumanReading();
  readingTitle.textContent = reading.title || "Your personal reading";
  readingIntro.textContent = reading.intro || "A calmer, clearer reading is ready.";

  renderTextCards(traitsList, reading.personality_traits || []);
  renderTextCards(emotionsList, reading.emotional_patterns || []);
  renderTextCards(relationshipsList, reading.relationship_patterns || []);
  renderTextCards(careerList, reading.career_and_money || []);
  renderTextCards(pastList, reading.past_patterns || []);
  renderTextCards(presentList, reading.current_phase || []);
  renderTextCards(futureList, reading.future_guidance || []);
  renderTextCards(strengthsList, reading.strengths_to_use || []);
  renderTextCards(watchList, reading.areas_to_watch || []);
  renderHighlightCards(highlightsList, reading.life_highlights || []);
  renderChatStarters(reading.chat_starters || []);

  rerunPretextLayout();
  revealSections();
}

function renderChatTranscript() {
  chatThread.innerHTML = "";
  if (!chatTranscript.length) {
    chatThreadSection.classList.add("hidden-block");
    return;
  }

  chatThreadSection.classList.remove("hidden-block");
  chatTranscript.forEach((message) => {
    const badge = message.role === "user" ? "You asked" : "ASL answered";
    chatThread.appendChild(buildNode(`
      <article class="chat-message ${message.role}">
        <p class="eyebrow">${escapeHtml(badge)}</p>
        <p>${escapeHtml(message.text)}</p>
      </article>
    `));
  });
  rerunPretextLayout();
}

function composeChatAnswer(result, query) {
  const reading = result.human_reading || fallbackHumanReading();
  const lowerQuery = query.toLowerCase();
  if (lowerQuery.includes("past")) {
    return [reading.intro, ...(reading.past_patterns || []).slice(0, 2)].join(" ");
  }
  if (lowerQuery.includes("future") || lowerQuery.includes("next")) {
    return [reading.intro, ...(reading.future_guidance || []).slice(0, 2)].join(" ");
  }
  if (/(love|relationship|marriage|partner|dating|romance)/.test(lowerQuery)) {
    return [reading.intro, ...(reading.relationship_patterns || []).slice(0, 2)].join(" ");
  }
  if (/(career|job|work|profession|money|finance|income|business)/.test(lowerQuery)) {
    return [reading.intro, ...(reading.career_and_money || []).slice(0, 2)].join(" ");
  }
  if (lowerQuery.includes("person") || lowerQuery.includes("trait") || lowerQuery.includes("nature")) {
    return [reading.intro, ...(reading.personality_traits || []).slice(0, 2)].join(" ");
  }
  return [
    reading.intro,
    ...(reading.current_phase || []).slice(0, 1),
    ...(reading.future_guidance || []).slice(0, 1),
  ].join(" ");
}

function fallbackHumanReading() {
  return {
    title: "Your personal reading",
    intro: "Your reading is ready, but some parts of the summary were unavailable. You can still ask a follow-up question below.",
    personality_traits: ["You come through as layered, thoughtful, and growth-oriented."],
    emotional_patterns: ["Your emotional world seems sensitive, deep, and shaped by a strong need for steadiness."],
    relationship_patterns: ["Your chart suggests that meaningful connection matters more to you than surface-level attention."],
    career_and_money: ["Your long-term progress looks strongest when you build steadily and avoid rushed decisions."],
    past_patterns: ["Your past seems to have shaped patience, resilience, and self-awareness."],
    current_phase: ["You are in a phase where clarity matters more than speed."],
    future_guidance: ["The next stretch rewards steadiness, better choices, and trust in gradual progress."],
    strengths_to_use: ["One of your strengths is the ability to grow through experience instead of collapsing under pressure."],
    areas_to_watch: ["The chart suggests taking extra care with pacing, patience, and emotional overextension."],
    life_highlights: ["You grow most when you stay honest with yourself and do not rush what needs time."],
    chat_starters: ["What should I focus on most right now?"],
  };
}

function inferLifeDomain(query) {
  const normalized = String(query || "").toLowerCase();
  if (!normalized.trim()) {
    return "general";
  }
  if (/(love|relationship|marriage|partner|dating|romance|wife|husband)/.test(normalized)) {
    return "relationships";
  }
  if (/(career|job|work|profession|promotion|boss|office)/.test(normalized)) {
    return "career";
  }
  if (/(money|finance|income|salary|wealth|business|earning)/.test(normalized)) {
    return "finance";
  }
  if (/(health|body|sleep|stress|energy|healing|illness)/.test(normalized)) {
    return "health";
  }
  if (/(spiritual|purpose|faith|karma|meaning|travel|growth)/.test(normalized)) {
    return "spirituality";
  }
  return "general";
}

function renderTextCards(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    container.appendChild(buildNode(`
      <article class="reading-item">
        <p>${escapeHtml(item)}</p>
      </article>
    `));
  });
}

function renderHighlightCards(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    container.appendChild(buildNode(`
      <article class="highlight-item">
        <p>${escapeHtml(item)}</p>
      </article>
    `));
  });
}

function renderChatStarters(items) {
  chatStarters.innerHTML = "";
  items.forEach((item) => {
    const button = buildNode(`
      <button type="button" class="starter-chip">
        ${escapeHtml(item)}
        <span>Tap to place this into the question box</span>
      </button>
    `);
    button.addEventListener("click", () => {
      followUpQuery.value = item;
      followUpQuery.focus();
    });
    chatStarters.appendChild(button);
  });
}

function enterResultMode() {
  appShell.classList.add("mode-result");
  intakeScreen.setAttribute("aria-hidden", "true");
  resultScreen.setAttribute("aria-hidden", "false");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function revealSections() {
  const reveals = Array.from(document.querySelectorAll(".result-screen .reveal"));
  reveals.forEach((element, index) => {
    element.classList.remove("is-visible");
    window.setTimeout(() => {
      element.classList.add("is-visible");
    }, 120 + index * 110);
  });
}

function buildNode(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function setBusy(form, busy) {
  Array.from(form.elements).forEach((element) => {
    element.disabled = busy;
  });
}

function setStatus(node, message, success = false) {
  node.textContent = message;
  node.classList.toggle("success", success);
}

function normalizeEmpty(value) {
  const normalized = String(value || "").trim();
  return normalized.length ? normalized : null;
}

function withSeconds(value) {
  if (!value) return value;
  return value.length === 5 ? `${value}:00` : value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function formatError(detail) {
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item.msg || item.message || "Invalid input").join(" ");
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return "The backend rejected the request.";
}

async function bootImmersiveFrontend() {
  await Promise.allSettled([initThreeScene(), initPretextLayout(), registerServiceWorker()]);
  bindInstallPrompt();
  restoreAppState();
}

let rerunPretextLayout = () => {};

async function initThreeScene() {
  if (!constellationCanvas) {
    return;
  }

  try {
    const THREE = await import("https://esm.sh/three@0.170.0");
    const renderer = new THREE.WebGLRenderer({
      canvas: constellationCanvas,
      alpha: true,
      antialias: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x080511, 0.055);

    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    camera.position.set(0, 0, 13);

    const cluster = new THREE.Group();
    scene.add(cluster);

    const pointCount = 320;
    const positions = new Float32Array(pointCount * 3);
    for (let i = 0; i < pointCount; i += 1) {
      const radius = 2 + Math.random() * 6.5;
      const theta = Math.random() * Math.PI * 2;
      const y = (Math.random() - 0.5) * 5.2;
      positions[i * 3] = Math.cos(theta) * radius;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = Math.sin(theta) * radius;
    }

    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const stars = new THREE.Points(
      starGeometry,
      new THREE.PointsMaterial({
        color: 0xf8e2b6,
        size: 0.06,
        transparent: true,
        opacity: 0.88,
      })
    );
    cluster.add(stars);

    const orb = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.1, 16),
      new THREE.MeshBasicMaterial({
        color: 0x8a63ff,
        wireframe: true,
        transparent: true,
        opacity: 0.2,
      })
    );
    cluster.add(orb);

    const rings = [];
    [2.4, 3.5, 5.1].forEach((radius, index) => {
      const points = [];
      for (let step = 0; step <= 96; step += 1) {
        const angle = (step / 96) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius * 0.42, 0));
      }
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(
        geometry,
        new THREE.LineBasicMaterial({
          color: index === 0 ? 0xf5c977 : index === 1 ? 0xb79bff : 0x6ba0ff,
          transparent: true,
          opacity: 0.22,
        })
      );
      line.rotation.x = 1.05 + index * 0.16;
      line.rotation.z = index * 0.72;
      rings.push(line);
      cluster.add(line);
    });

    const glowLight = new THREE.PointLight(0xb79bff, 1.4, 30);
    glowLight.position.set(0, 0, 4);
    const warmLight = new THREE.PointLight(0xf5c977, 0.9, 20);
    warmLight.position.set(-5, 2, 6);
    scene.add(glowLight, warmLight);

    function resize() {
      const width = window.innerWidth;
      const height = window.innerHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }

    let frameId = 0;
    function animate() {
      frameId = window.requestAnimationFrame(animate);
      const now = Date.now() * 0.0002;
      cluster.rotation.y += 0.0009;
      cluster.rotation.x = Math.sin(now * 1.8) * 0.06;
      orb.rotation.x += 0.002;
      orb.rotation.y += 0.0016;
      rings.forEach((ring, index) => {
        ring.rotation.z += 0.0004 + index * 0.00015;
      });
      renderer.render(scene, camera);
    }

    resize();
    animate();
    window.addEventListener("resize", debounce(resize, 120));
    window.addEventListener("beforeunload", () => {
      window.cancelAnimationFrame(frameId);
      renderer.dispose();
      starGeometry.dispose();
    });
  } catch (error) {
    console.warn("Three.js background unavailable, continuing without it.", error);
  }
}

async function initPretextLayout() {
  const pretextTargets = Array.from(document.querySelectorAll("[data-pretext]"));
  if (!pretextTargets.length) {
    return;
  }

  try {
    const { prepareWithSegments, layoutWithLines } = await import("https://esm.sh/@chenglou/pretext");
    const cache = new WeakMap();

    const renderAll = () => {
      pretextTargets.forEach((node) => {
        const originalText = node.dataset.pretextSource || node.textContent.trim();
        node.dataset.pretextSource = originalText;

        const styles = window.getComputedStyle(node);
        const width = Math.max(node.clientWidth, 120);
        const fontSize = styles.fontSize;
        const fontWeight = styles.fontWeight || "700";
        const fontFamily = styles.fontFamily;
        const lineHeight = Number.parseFloat(styles.lineHeight) || Math.round(Number.parseFloat(fontSize) * 1.04);
        const font = `${fontWeight} ${fontSize} ${fontFamily}`;

        const cached = cache.get(node);
        if (!cached || cached.text !== originalText || cached.font !== font) {
          cache.set(node, {
            text: originalText,
            font,
            prepared: prepareWithSegments(originalText, font),
          });
        }

        const prepared = cache.get(node).prepared;
        const { lines } = layoutWithLines(prepared, width, lineHeight);
        node.innerHTML = lines
          .map((line) => `<span class="pretext-line">${escapeHtml(line.text)}</span>`)
          .join("");
      });
    };

    rerunPretextLayout = renderAll;
    renderAll();
    window.addEventListener("resize", debounce(renderAll, 120));
  } catch (error) {
    console.warn("Pretext layout unavailable, falling back to normal text flow.", error);
  }
}

function debounce(fn, waitMs) {
  let timeoutId = 0;
  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => fn(...args), waitMs);
  };
}

function persistAppState() {
  const state = {
    latestBirthData,
    latestRenderedReading,
    chatTranscript,
    mode: appShell.classList.contains("mode-result") ? "result" : "intake",
  };
  window.sessionStorage.setItem("asl-app-state", JSON.stringify(state));
}

function restoreAppState() {
  try {
    const raw = window.sessionStorage.getItem("asl-app-state");
    if (!raw) return;
    const state = JSON.parse(raw);
    latestBirthData = state.latestBirthData || null;
    latestRenderedReading = state.latestRenderedReading || null;
    chatTranscript = Array.isArray(state.chatTranscript) ? state.chatTranscript : [];
    if (state.mode === "result" && latestRenderedReading) {
      renderHumanReading(latestRenderedReading);
      renderChatTranscript();
      enterResultMode();
    }
  } catch (error) {
    console.warn("Unable to restore app state.", error);
  }
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  try {
    await navigator.serviceWorker.register("./sw.js", { scope: "./" });
  } catch (error) {
    console.warn("Service worker registration failed.", error);
  }
}

function bindInstallPrompt() {
  if (!installAppButton) {
    return;
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    installAppButton.classList.remove("hidden-block");
  });

  installAppButton.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      return;
    }

    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice.catch(() => null);
    deferredInstallPrompt = null;
    installAppButton.classList.add("hidden-block");
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    installAppButton.classList.add("hidden-block");
  });
}
