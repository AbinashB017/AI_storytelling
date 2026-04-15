/**
 * Scenova — app.js (Cinematic Visual Director Edition)
 * Refactored for Anamorphic Frame Design System
 */

// ─── Config ────────────────────────────────────────────────────────────────
const API_BASE    = "http://localhost:8000";
const AUTOPLAY_MS = 4000; // Slightly longer for cinematic immersion

// ─── State ─────────────────────────────────────────────────────────────────
let panels        = [];
let currentIndex  = 0;
let autoTimer     = null;
let isAutoplaying = false;
let hoverPaused   = false;
let isGridView    = false;

// ─── DOM refs ──────────────────────────────────────────────────────────────
const inputSection      = document.getElementById("input-section");
const storyboardSection = document.getElementById("storyboard-section");
const loadingOverlay    = document.getElementById("loading-overlay");
const narrativeInput    = document.getElementById("narrative-input");
const charCountEl       = document.getElementById("char-count");
const errorMsg          = document.getElementById("error-msg");
const generateBtn       = document.getElementById("generate-btn");
const btnText           = document.getElementById("btn-text");
const btnLoader         = document.getElementById("btn-loader");
const btnIconInner      = document.getElementById("btn-icon-inner");

const slideshowView   = document.getElementById("slideshow-view");
const slideTrack      = document.getElementById("slide-track");
const gridView        = document.getElementById("grid-view");
const panelGrid       = document.getElementById("panel-grid");
const currentSlideNum = document.getElementById("current-slide-num");
const totalSlidesEl   = document.getElementById("total-slides");
const slideHeadline   = document.getElementById("slide-headline");
const slideCaption    = document.getElementById("slide-caption");
const slideRoleTag    = document.getElementById("slide-role-tag");
const dotRow          = document.getElementById("dot-row");
const prevBtn         = document.getElementById("prev-btn");
const nextBtn         = document.getElementById("next-btn");

// Global Autoplay Toggle (Header icon)
const autoplayIcon    = document.getElementById("autoplay-icon");
// View Toggle Buttons (Grid/Slideshow)
const viewToggleGrid  = document.getElementById("view-toggle-grid");
const viewToggleSlide = document.getElementById("view-toggle-slideshow");

const loadingSteps = [
  document.getElementById("step-1"),
  document.getElementById("step-2"),
  document.getElementById("step-3"),
  document.getElementById("step-4"),
  document.getElementById("step-5"),
];

// ─── Event Listeners ───────────────────────────────────────────────────────
narrativeInput.addEventListener("input", () => {
  charCountEl.textContent = narrativeInput.value.length;
});

document.addEventListener("keydown", (e) => {
  if (storyboardSection.classList.contains("hidden")) return;
  if (e.key === "ArrowRight") nextSlide();
  if (e.key === "ArrowLeft")  prevSlide();
  if (e.key === "Escape")     backToInput();
  if (e.key === " ")          { e.preventDefault(); toggleAutoplay(); }
});

// ══════════════════════════════════════════════════════════════════════════
//  GENERATE
// ══════════════════════════════════════════════════════════════════════════
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
      throw new Error("No panels generated. Try a more detailed narrative.");

    panels = data.panels;
    buildSlideshow();
    buildGrid();
    showSlide(0);
    openStoryboard();

  } catch (err) {
    console.error("[ERROR]", err);
    showError(err.message || "Failed to generate storyboard. Please try again.");
  } finally {
    setLoading(false);
    hideLoadingOverlay();
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  IMAGE HELPER
// ══════════════════════════════════════════════════════════════════════════
function resolveImageSrc(imageUrl) {
  if (!imageUrl) return "";
  if (imageUrl.startsWith("http")) return imageUrl;
  return `data:image/png;base64,${imageUrl}`;
}

function makeImg(panel, idx, onLoad, onError) {
  const img = document.createElement("img");
  img.alt   = `Scene ${idx + 1}`;
  img.className = "w-full h-full object-cover";
  img.onload  = onLoad;
  img.onerror = onError;
  img.src = resolveImageSrc(panel.image_url);
  return img;
}

// ══════════════════════════════════════════════════════════════════════════
//  BUILD SLIDESHOW
// ══════════════════════════════════════════════════════════════════════════
function buildSlideshow() {
  slideTrack.innerHTML = "";
  dotRow.innerHTML     = "";
  totalSlidesEl.textContent = panels.length;

  panels.forEach((panel, idx) => {
    const slide = document.createElement("div");
    slide.className = "slide";
    slide.id = `slide-${idx}`;

    const skel = document.createElement("div");
    skel.className = "slide-skeleton";
    slide.appendChild(skel);

    const img = makeImg(
      panel,
      idx,
      () => {
        if (slide.contains(skel)) slide.removeChild(skel);
        slide.appendChild(img);
      },
      () => {
        console.error(`[SCENOVA] Image ${idx + 1} failed to load`);
        skel.style.background = "var(--surface-container-high)";
        skel.style.animation  = "none";
        skel.innerHTML = `<p style="color:var(--outline-variant);text-size:0.75rem;">Scene unavailable</p>`;
      }
    );

    slideTrack.appendChild(slide);

    // Dot
    const dot = document.createElement("div");
    dot.className = "dot";
    dot.onclick   = () => { stopAutoplay(); showSlide(idx); };
    dotRow.appendChild(dot);
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  BUILD GRID
// ══════════════════════════════════════════════════════════════════════════
function buildGrid() {
  panelGrid.innerHTML = "";

  panels.forEach((panel, idx) => {
    const card = document.createElement("div");
    card.className = "group relative aspect-[16/9] glass-card rounded-lg overflow-hidden border border-outline-variant/10 hover:border-primary-container/30 transition-all cursor-pointer";
    card.onclick   = () => { switchToSlideshow(); showSlide(idx); };

    // Placeholder Overlay
    const overlay = document.createElement("div");
    overlay.className = "absolute inset-0 bg-surface-container-lowest/40 opacity-100 group-hover:opacity-0 transition-opacity z-10";

    const badge = document.createElement("div");
    badge.className = "absolute bottom-4 left-4 z-20";
    badge.innerHTML = `<span class="bg-surface-container-highest/80 backdrop-blur-md px-2 py-1 text-[10px] font-bold rounded">SCENE ${idx + 1}</span>`;

    const skel = document.createElement("div");
    skel.className = "panel-card-skeleton";
    card.appendChild(skel);

    const img = makeImg(
      panel,
      idx,
      () => {
        if (card.contains(skel)) card.removeChild(skel);
        img.className = "w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 grayscale group-hover:grayscale-0";
        card.appendChild(img);
        card.appendChild(overlay);
        card.appendChild(badge);
      },
      () => { 
        skel.style.animation = "none";
        skel.innerHTML = `<span class="text-[10px] text-outline-variant">Unavailable</span>`;
      }
    );

    panelGrid.appendChild(card);
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  SLIDE CONTROL
// ══════════════════════════════════════════════════════════════════════════
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
  slideRoleTag.textContent    = `SCENE ${String(index + 1).padStart(2, '0')} / ${(panel.narrative_role || "").replace(/_/g, " ").toUpperCase()}`;
  currentSlideNum.textContent = index + 1;

  prevBtn.disabled = index === 0;
  nextBtn.disabled = index === panels.length - 1;
  prevBtn.classList.toggle("opacity-20", index === 0);
  nextBtn.classList.toggle("opacity-20", index === panels.length - 1);
}

function nextSlide() {
  if (currentIndex < panels.length - 1) showSlide(currentIndex + 1);
  else if (isAutoplaying) showSlide(0);
}

function prevSlide() {
  if (currentIndex > 0) showSlide(currentIndex - 1);
}

// ══════════════════════════════════════════════════════════════════════════
//  AUTOPLAY
// ══════════════════════════════════════════════════════════════════════════
function toggleAutoplay() {
  isAutoplaying ? stopAutoplay() : startAutoplay();
}

function startAutoplay() {
  isAutoplaying = true;
  if (autoplayIcon) {
    autoplayIcon.textContent = "pause_circle";
    autoplayIcon.parentElement.classList.add("text-primary");
  }
  autoTimer = setInterval(() => {
    showSlide((currentIndex + 1) % panels.length);
  }, AUTOPLAY_MS);
}

function stopAutoplay() {
  isAutoplaying = false;
  clearInterval(autoTimer);
  autoTimer = null;
  if (autoplayIcon) {
    autoplayIcon.textContent = "play_circle";
    autoplayIcon.parentElement.classList.remove("text-primary");
  }
  hoverPaused = false;
}

// ══════════════════════════════════════════════════════════════════════════
//  VIEW TOGGLE
// ══════════════════════════════════════════════════════════════════════════
function switchToGrid() {
  isGridView = true;
  stopAutoplay();
  slideshowView.classList.add("hidden");
  gridView.classList.remove("hidden");
  
  viewToggleGrid.classList.add("text-primary", "bg-primary/10", "rounded");
  viewToggleGrid.classList.remove("text-on-surface-variant");
  viewToggleSlide.classList.remove("text-primary", "bg-primary/10", "rounded");
  viewToggleSlide.classList.add("text-on-surface-variant");
}

function switchToSlideshow() {
  isGridView = false;
  gridView.classList.add("hidden");
  slideshowView.classList.remove("hidden");

  viewToggleSlide.classList.add("text-primary", "bg-primary/10", "rounded");
  viewToggleSlide.classList.remove("text-on-surface-variant");
  viewToggleGrid.classList.remove("text-primary", "bg-primary/10", "rounded");
  viewToggleGrid.classList.add("text-on-surface-variant");
}

// ══════════════════════════════════════════════════════════════════════════
//  SECTION TRANSITIONS
// ══════════════════════════════════════════════════════════════════════════
function openStoryboard() {
  inputSection.classList.add("hidden");
  storyboardSection.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function backToInput() {
  stopAutoplay();
  switchToSlideshow();
  storyboardSection.classList.add("hidden");
  inputSection.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ══════════════════════════════════════════════════════════════════════════
//  DOWNLOAD STORYBOARD HTML
// ══════════════════════════════════════════════════════════════════════════
function downloadStoryboard() {
  if (panels.length === 0) return;
  
  const cards = panels.map((p, i) => {
    const src = resolveImageSrc(p.image_url);
    return `
    <div class="card">
      <div class="card-img-wrap">
        <img src="${src}" alt="Scene ${i + 1}" />
        <div class="card-badge">Scene ${i + 1}</div>
      </div>
      <div class="card-body">
        <div class="card-role">${escHtml((p.narrative_role || "").replace(/_/g, " ").toUpperCase())}</div>
        <div class="card-headline">${escHtml(p.headline || "")}</div>
        <div class="card-caption">${escHtml(p.caption || "")}</div>
      </div>
    </div>`;
  }).join("\n");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Scenova Visual Stream</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',sans-serif;background:#0a0e13;color:#e0e2ea;min-height:100vh;padding:48px 24px}
    header{text-align:center;margin-bottom:48px}
    .logo{font-family:'Space Grotesk',sans-serif;font-size:2rem;font-weight:700;letter-spacing:-0.04em;margin-bottom:8px;text-transform:uppercase}
    .logo span{color:#00d1ff}
    .tagline{color:#bbc9cf;font-size:0.9rem;font-weight:300}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:24px;max-width:1400px;margin:0 auto}
    .card{background:#1c2025;border:1px solid rgba(60,73,78,0.2);border-radius:8px;overflow:hidden;transition:all .3s ease}
    .card:hover{transform:translateY(-4px);box-shadow:0 20px 40px rgba(0,0,0,0.5);border-color:#00d1ff}
    .card-img-wrap{position:relative}
    .card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
    .card-badge{position:absolute;top:12px;left:12px;background:rgba(10,14,19,0.8);backdrop-filter:blur(8px);border:1px solid rgba(0,209,255,0.3);border-radius:4px;color:#00d1ff;font-size:0.6rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:4px 10px}
    .card-body{padding:20px}
    .card-role{font-size:0.6rem;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#00d1ff;margin-bottom:8px}
    .card-headline{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:700;margin-bottom:8px;line-height:1.3;color:#E6EDF3}
    .card-caption{font-size:0.85rem;color:#bbc9cf;line-height:1.6;font-style:italic;font-weight:300}
    footer{text-align:center;margin-top:80px;color:#3c494e;font-size:0.75rem;letter-spacing:0.05em;text-transform:uppercase}
  </style>
</head>
<body>
  <header>
    <div class="logo">SCENOVA <span>DIRECTOR</span></div>
    <div class="tagline">Automated Cinematic Visual Direction</div>
  </header>
  <div class="grid">
    ${cards}
  </div>
  <footer>Generated via Scenova AI Neural Engine</footer>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `scenova-${Date.now()}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

// ══════════════════════════════════════════════════════════════════════════
//  LOADING
// ══════════════════════════════════════════════════════════════════════════
function showLoadingOverlay() {
  loadingSteps.forEach(s => s.classList.remove("active", "done"));
  loadingSteps[0].classList.add("active");
  loadingOverlay.classList.remove("hidden");
}

function hideLoadingOverlay() {
  loadingOverlay.classList.add("hidden");
}

async function animateLoadingSteps() {
  const delays = [400, 1200, 2200, 3500, 4800];
  for (let i = 0; i < loadingSteps.length; i++) {
    await sleep(delays[i]);
    if (i > 0) loadingSteps[i - 1].classList.replace("active", "done");
    loadingSteps[i].classList.add("active");
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  UI HELPERS
// ══════════════════════════════════════════════════════════════════════════
function setLoading(on) {
  generateBtn.disabled = on;
  btnText.classList.toggle("hidden", on);
  btnLoader.classList.toggle("hidden", !on);
  if (btnIconInner) btnIconInner.classList.toggle("hidden", on);
}

function showError(msg) {
  errorMsg.textContent = `⚠ ${msg}`;
  errorMsg.classList.remove("hidden");
}

function hideError() {
  errorMsg.classList.add("hidden");
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}
