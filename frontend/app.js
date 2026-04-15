/**
 * AI Storyboard Generator — app.js v3
 * Slideshow + Grid view | Autoplay | Download | Headline/Caption | Keyboard nav
 */

// ─── Config ────────────────────────────────────────────────────────────────
const API_BASE        = "http://localhost:8000";
const AUTOPLAY_MS     = 4000;

// ─── State ─────────────────────────────────────────────────────────────────
let panels        = [];
let currentIndex  = 0;
let autoTimer     = null;
let isAutoplaying = false;
let hoverPaused   = false;
let isGridView    = false;

// ─── DOM ───────────────────────────────────────────────────────────────────
const inputSection      = document.getElementById("input-section");
const storyboardSection = document.getElementById("storyboard-section");
const loadingOverlay    = document.getElementById("loading-overlay");
const narrativeInput    = document.getElementById("narrative-input");
const charCountEl       = document.getElementById("char-count");
const errorMsg          = document.getElementById("error-msg");
const generateBtn       = document.getElementById("generate-btn");
const btnText           = document.getElementById("btn-text");
const btnLoader         = document.getElementById("btn-loader");

const slideshowView   = document.getElementById("slideshow-view");
const slideTrack      = document.getElementById("slide-track");
const gridView        = document.getElementById("grid-view");
const panelGrid       = document.getElementById("panel-grid");
const currentSlideNum = document.getElementById("current-slide-num");
const totalSlidesEl   = document.getElementById("total-slides");
const slideHeadline   = document.getElementById("slide-headline");
const slideCaption    = document.getElementById("slide-caption");
const dotRow          = document.getElementById("dot-row");
const prevBtn         = document.getElementById("prev-btn");
const nextBtn         = document.getElementById("next-btn");
const autoplayBtn     = document.getElementById("autoplay-btn");
const viewToggleBtn   = document.getElementById("view-toggle-btn");

const loadingSteps = [
  document.getElementById("step-1"),
  document.getElementById("step-2"),
  document.getElementById("step-3"),
  document.getElementById("step-4"),
  document.getElementById("step-5"),
];

// ─── Char counter ──────────────────────────────────────────────────────────
narrativeInput.addEventListener("input", () => {
  charCountEl.textContent = narrativeInput.value.length;
});

// ─── Keyboard nav ──────────────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (storyboardSection.classList.contains("hidden")) return;
  if (e.key === "ArrowRight") nextSlide();
  if (e.key === "ArrowLeft")  prevSlide();
  if (e.key === "Escape")     backToInput();
  if (e.key === " ")          { e.preventDefault(); toggleAutoplay(); }
});

// ─── GENERATE ──────────────────────────────────────────────────────────────
async function generateStoryboard() {
  const text  = narrativeInput.value.trim();
  const style = document.getElementById("style-select").value;

  if (text.length < 20) {
    showError("Please enter at least a few sentences to describe your story.");
    return;
  }
  hideError();
  setLoading(true);
  showLoadingOverlay();

  try {
    await animateLoadingSteps();

    const res = await fetch(`${API_BASE}/api/v1/generate-storyboard`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ text, style }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    if (!data.panels || data.panels.length === 0)
      throw new Error("No panels were generated. Try a more detailed narrative.");

    panels = data.panels;
    buildSlideshow();
    buildGrid();
    showSlide(0);
    openStoryboard();

  } catch (err) {
    showError(err.message || "Failed to generate storyboard. Please try again.");
  } finally {
    setLoading(false);
    hideLoadingOverlay();
  }
}

// ─── BUILD SLIDESHOW ───────────────────────────────────────────────────────
function buildSlideshow() {
  slideTrack.innerHTML = "";
  dotRow.innerHTML     = "";
  totalSlidesEl.textContent = panels.length;

  panels.forEach((panel, idx) => {
    // Slide
    const slide = document.createElement("div");
    slide.className = "slide";
    slide.id = `slide-${idx}`;

    const skel = document.createElement("div");
    skel.className = "slide-skeleton";
    slide.appendChild(skel);

    const img = document.createElement("img");
    img.alt = `Scene ${idx + 1}`;

    img.onload = () => {
      if (slide.contains(skel)) slide.removeChild(skel);
      slide.appendChild(img);
    };
    img.onerror = (e) => {
      console.error("[IMAGE ERROR]", img.src);
      skel.style.background = "var(--surface-2)";
      skel.style.animation  = "none";
      skel.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:40px;">Image unavailable</p>`;
    };

    console.log("[IMAGE]", idx + 1, panel.image_url ? panel.image_url.substring(0, 60) : "EMPTY");

    if (panel.image_url && panel.image_url.startsWith("http")) {
      img.src = panel.image_url;
    } else if (panel.image_url) {
      img.src = `data:image/png;base64,${panel.image_url}`;
    }

    slideTrack.appendChild(slide);

    // Dot
    const dot = document.createElement("div");
    dot.className = "dot";
    dot.onclick   = () => showSlide(idx);
    dotRow.appendChild(dot);
  });
}

// ─── BUILD GRID ────────────────────────────────────────────────────────────
function buildGrid() {
  panelGrid.innerHTML = "";

  panels.forEach((panel, idx) => {
    const card = document.createElement("div");
    card.className = "panel-card";
    card.onclick   = () => { switchToSlideshow(); showSlide(idx); };

    const imgWrap = document.createElement("div");
    const skel    = document.createElement("div");
    skel.className = "panel-card-skeleton";
    imgWrap.appendChild(skel);

    const img = document.createElement("img");
    img.alt = `Scene ${idx + 1}`;

    img.onload = () => {
      if (imgWrap.contains(skel)) imgWrap.removeChild(skel);
      imgWrap.appendChild(img);
    };
    img.onerror = () => {
      skel.style.animation = "none";
    };

    if (panel.image_url && panel.image_url.startsWith("http")) {
      img.src = panel.image_url;
    } else if (panel.image_url) {
      img.src = `data:image/png;base64,${panel.image_url}`;
    }

    const body = document.createElement("div");
    body.className = "panel-card-body";
    body.innerHTML = `
      <div class="panel-card-num">Scene ${idx + 1} · ${(panel.narrative_role || "").replace(/_/g," ").toUpperCase()}</div>
      <div class="panel-card-headline">${panel.headline || ""}</div>
      <div class="panel-card-caption">${panel.caption || ""}</div>
    `;

    card.appendChild(imgWrap);
    card.appendChild(body);
    panelGrid.appendChild(card);
  });
}

// ─── SHOW SLIDE ────────────────────────────────────────────────────────────
function showSlide(index) {
  if (index < 0 || index >= panels.length) return;

  document.querySelectorAll(".slide").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".dot").forEach(d => d.classList.remove("active"));

  currentIndex = index;
  document.getElementById(`slide-${index}`)?.classList.add("active");
  document.querySelectorAll(".dot")[index]?.classList.add("active");

  const panel = panels[index];
  slideHeadline.textContent   = panel.headline || "";
  slideCaption.textContent    = panel.caption  || "";
  currentSlideNum.textContent = index + 1;

  prevBtn.disabled = index === 0;
  nextBtn.disabled = index === panels.length - 1;
}

function nextSlide() {
  if (currentIndex < panels.length - 1) showSlide(currentIndex + 1);
  else if (isAutoplaying) showSlide(0);
}

function prevSlide() {
  if (currentIndex > 0) showSlide(currentIndex - 1);
}

// ─── AUTOPLAY ──────────────────────────────────────────────────────────────
function toggleAutoplay() {
  isAutoplaying ? stopAutoplay() : startAutoplay();
}
function startAutoplay() {
  isAutoplaying = true;
  autoplayBtn.textContent = "⏸ Pause";
  autoplayBtn.classList.add("active");
  autoTimer = setInterval(() => showSlide((currentIndex + 1) % panels.length), AUTOPLAY_MS);
}
function stopAutoplay() {
  isAutoplaying = false;
  clearInterval(autoTimer);
  autoTimer = null;
  autoplayBtn.textContent = "▶ Autoplay";
  autoplayBtn.classList.remove("active");
}
function pauseAutoplay() {
  if (isAutoplaying) { clearInterval(autoTimer); autoTimer = null; hoverPaused = true; }
}
function resumeAutoplay() {
  if (hoverPaused && isAutoplaying) {
    autoTimer = setInterval(() => showSlide((currentIndex + 1) % panels.length), AUTOPLAY_MS);
    hoverPaused = false;
  }
}

// ─── VIEW TOGGLE ───────────────────────────────────────────────────────────
function toggleView() {
  isGridView ? switchToSlideshow() : switchToGrid();
}
function switchToGrid() {
  isGridView = true;
  slideshowView.classList.add("hidden");
  gridView.classList.remove("hidden");
  viewToggleBtn.textContent = "▶ Slideshow";
  stopAutoplay();
}
function switchToSlideshow() {
  isGridView = false;
  gridView.classList.add("hidden");
  slideshowView.classList.remove("hidden");
  viewToggleBtn.textContent = "⊞ Grid View";
}

// ─── SECTION TRANSITIONS ───────────────────────────────────────────────────
function openStoryboard() {
  inputSection.classList.add("hidden");
  storyboardSection.classList.remove("hidden");
}
function backToInput() {
  stopAutoplay();
  storyboardSection.classList.add("hidden");
  inputSection.classList.remove("hidden");
  switchToSlideshow();
}

// ─── DOWNLOAD STORYBOARD ───────────────────────────────────────────────────
function downloadStoryboard() {
  const cards = panels.map((p, i) => {
    const src = p.image_url
      ? (p.image_url.startsWith("http") ? p.image_url : `data:image/png;base64,${p.image_url}`)
      : "";

    return `
    <div class="card">
      <div class="card-num">Scene ${i + 1} · ${(p.narrative_role || "").replace(/_/g," ").toUpperCase()}</div>
      <img src="${src}" alt="Scene ${i + 1}" />
      <div class="card-body">
        <div class="card-headline">${p.headline || ""}</div>
        <div class="card-caption">${p.caption || ""}</div>
      </div>
    </div>`;
  }).join("\n");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>My Storyboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',sans-serif;background:#07090f;color:#f0f4f8;min-height:100vh;padding:40px 24px}
    h1{font-family:'Playfair Display',serif;font-size:2rem;text-align:center;margin-bottom:40px;color:#e8a43c}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:24px;max-width:1200px;margin:0 auto}
    .card{background:#0d1117;border:1px solid rgba(255,255,255,0.08);border-radius:18px;overflow:hidden}
    .card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
    .card-body{padding:16px 18px 20px}
    .card-num{font-size:0.68rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#e8a43c;margin-bottom:6px}
    .card-headline{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;margin-bottom:6px;line-height:1.35}
    .card-caption{font-size:0.82rem;color:#8a9bb0;line-height:1.6;font-style:italic}
  </style>
</head>
<body>
  <h1>🎬 My Storyboard</h1>
  <div class="grid">
    ${cards}
  </div>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = "storyboard.html";
  a.click();
  URL.revokeObjectURL(url);
}

// ─── LOADING ───────────────────────────────────────────────────────────────
function showLoadingOverlay() {
  loadingSteps.forEach(s => s.classList.remove("active","done"));
  loadingSteps[0].classList.add("active");
  loadingOverlay.classList.remove("hidden");
}
function hideLoadingOverlay() {
  loadingOverlay.classList.add("hidden");
}
async function animateLoadingSteps() {
  const delays = [300, 900, 1800, 2800, 3800];
  for (let i = 0; i < loadingSteps.length; i++) {
    await sleep(delays[i]);
    if (i > 0) loadingSteps[i - 1].classList.replace("active", "done");
    loadingSteps[i].classList.add("active");
  }
}

// ─── UI HELPERS ────────────────────────────────────────────────────────────
function setLoading(on) {
  generateBtn.disabled = on;
  btnText.classList.toggle("hidden", on);
  btnLoader.classList.toggle("hidden", !on);
  document.querySelector(".btn-icon").classList.toggle("hidden", on);
}
function showError(msg) {
  errorMsg.textContent = `⚠ ${msg}`;
  errorMsg.classList.remove("hidden");
}
function hideError() {
  errorMsg.classList.add("hidden");
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
