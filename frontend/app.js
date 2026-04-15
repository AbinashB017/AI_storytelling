/**
 * AI Storyboard Generator — app.js
 * Full-screen slideshow with autoplay, keyboard nav, and API integration.
 */

// ─── Configuration ────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";   // Change to your deployed Render URL
const AUTOPLAY_INTERVAL = 4000;             // ms between slides

// ─── State ────────────────────────────────────────────────────────────────
let panels        = [];
let currentIndex  = 0;
let autoplayTimer = null;
let isAutoplaying = false;

// ─── DOM Refs ─────────────────────────────────────────────────────────────
const inputSection    = document.getElementById("input-section");
const slideshowSection = document.getElementById("slideshow-section");
const loadingOverlay  = document.getElementById("loading-overlay");
const narrativeInput  = document.getElementById("narrative-input");
const charCount       = document.getElementById("char-count");
const errorMsg        = document.getElementById("error-msg");
const generateBtn     = document.getElementById("generate-btn");
const btnText         = document.getElementById("btn-text");
const btnLoader       = document.getElementById("btn-loader");
const slideContainer  = document.getElementById("slide-container");
const currentSlideNum = document.getElementById("current-slide-num");
const totalSlides     = document.getElementById("total-slides");
const slideCaption    = document.getElementById("slide-caption");
const slideRole       = document.getElementById("slide-role");
const dotRow          = document.getElementById("dot-row");
const prevBtn         = document.getElementById("prev-btn");
const nextBtn         = document.getElementById("next-btn");
const autoplayBtn     = document.getElementById("autoplay-btn");

// Loading steps
const loadingSteps = [
  document.getElementById("step-1"),
  document.getElementById("step-2"),
  document.getElementById("step-3"),
  document.getElementById("step-4"),
  document.getElementById("step-5"),
];

// ─── Character Counter ────────────────────────────────────────────────────
narrativeInput.addEventListener("input", () => {
  charCount.textContent = narrativeInput.value.length;
});

// ─── Keyboard Navigation ──────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (slideshowSection.classList.contains("hidden")) return;
  if (e.key === "ArrowRight") nextSlide();
  if (e.key === "ArrowLeft")  prevSlide();
  if (e.key === "Escape")     backToInput();
  if (e.key === " ")          { e.preventDefault(); toggleAutoplay(); }
});

// ─── Pause autoplay on image hover ────────────────────────────────────────
let hoverPaused = false;
document.getElementById("slide-viewport").addEventListener("mouseenter", () => {
  if (isAutoplaying) { clearAutoplay(); hoverPaused = true; }
});
document.getElementById("slide-viewport").addEventListener("mouseleave", () => {
  if (hoverPaused) { startAutoplay(); hoverPaused = false; }
});

// ─── Generate Storyboard ─────────────────────────────────────────────────
async function generateStoryboard() {
  const text  = narrativeInput.value.trim();
  const style = document.getElementById("style-select").value;

  // Basic validation
  if (text.length < 20) {
    showError("Please enter at least a few sentences to describe your story.");
    return;
  }
  hideError();

  setLoading(true);
  showLoadingOverlay();

  try {
    // Animate loading steps
    await animateLoadingSteps();

    const response = await fetch(`${API_BASE}/api/v1/generate-storyboard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${response.status})`);
    }

    const data = await response.json();

    if (!data.panels || data.panels.length === 0) {
      throw new Error("No panels were generated. Try a more detailed narrative.");
    }

    panels = data.panels;
    buildSlideshow();
    showSlide(0);
    openSlideshow();

  } catch (err) {
    showError(err.message || "Something went wrong. Please try again.");
  } finally {
    setLoading(false);
    hideLoadingOverlay();
  }
}

// ─── Loading Overlay ──────────────────────────────────────────────────────
function showLoadingOverlay() {
  loadingSteps.forEach(s => { s.classList.remove("active", "done"); });
  loadingSteps[0].classList.add("active");
  loadingOverlay.classList.remove("hidden");
}

function hideLoadingOverlay() {
  loadingOverlay.classList.add("hidden");
}

async function animateLoadingSteps() {
  const delays = [400, 900, 1600, 2400, 3200];
  for (let i = 0; i < loadingSteps.length; i++) {
    await sleep(delays[i]);
    if (i > 0) loadingSteps[i - 1].classList.replace("active", "done");
    loadingSteps[i].classList.add("active");
  }
}

// ─── Build Slideshow Panels ───────────────────────────────────────────────
function buildSlideshow() {
  slideContainer.innerHTML = "";
  dotRow.innerHTML = "";

  panels.forEach((panel, idx) => {
    // Create slide
    const slide = document.createElement("div");
    slide.className = "slide";
    slide.id = `slide-${idx}`;

    const skeleton = document.createElement("div");
    skeleton.className = "slide-skeleton";

    const img = document.createElement("img");
    img.alt = `Scene ${idx + 1}`;
    img.loading = "lazy";

    // Show skeleton until image loads
    slide.appendChild(skeleton);
    img.onload = () => {
      if (slide.contains(skeleton)) slide.removeChild(skeleton);
      slide.appendChild(img);
    };
    img.onerror = () => {
      skeleton.style.background = "var(--surface-2)";
      skeleton.style.animation  = "none";
      skeleton.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:40px;font-size:0.9rem;">Image unavailable</p>`;
    };
    img.src = panel.image_url;

    slideContainer.appendChild(slide);

    // Create dot
    const dot = document.createElement("div");
    dot.className = "dot";
    dot.onclick = () => showSlide(idx);
    dotRow.appendChild(dot);
  });

  totalSlides.textContent = panels.length;
}

// ─── Slide Control ────────────────────────────────────────────────────────
function showSlide(index) {
  if (index < 0 || index >= panels.length) return;

  const allSlides = document.querySelectorAll(".slide");
  const allDots   = document.querySelectorAll(".dot");

  allSlides.forEach(s => s.classList.remove("active"));
  allDots.forEach(d => d.classList.remove("active"));

  currentIndex = index;
  allSlides[index]?.classList.add("active");
  allDots[index]?.classList.add("active");

  // Update caption and metadata
  const panel = panels[index];
  slideCaption.textContent = panel.caption || "";
  slideRole.textContent    = panel.narrative_role
    ? panel.narrative_role.replace(/_/g, " ").toUpperCase()
    : "";

  // Update counter
  currentSlideNum.textContent = index + 1;

  // Update nav buttons
  prevBtn.disabled = index === 0;
  nextBtn.disabled = index === panels.length - 1;
}

function nextSlide() {
  if (currentIndex < panels.length - 1) {
    showSlide(currentIndex + 1);
  } else if (isAutoplaying) {
    // Loop back from the end during autoplay
    showSlide(0);
  }
}

function prevSlide() {
  if (currentIndex > 0) showSlide(currentIndex - 1);
}

// ─── Autoplay ─────────────────────────────────────────────────────────────
function toggleAutoplay() {
  isAutoplaying ? stopAutoplay() : startAutoplay();
}

function startAutoplay() {
  isAutoplaying = true;
  autoplayBtn.textContent = "⏸ Pause";
  autoplayBtn.classList.add("active");
  autoplayTimer = setInterval(() => {
    const next = (currentIndex + 1) % panels.length;
    showSlide(next);
  }, AUTOPLAY_INTERVAL);
}

function stopAutoplay() {
  clearAutoplay();
  autoplayBtn.textContent = "▶ Autoplay";
  autoplayBtn.classList.remove("active");
}

function clearAutoplay() {
  isAutoplaying = false;
  clearInterval(autoplayTimer);
  autoplayTimer = null;
}

// ─── Section Transitions ──────────────────────────────────────────────────
function openSlideshow() {
  inputSection.classList.add("hidden");
  slideshowSection.classList.remove("hidden");
}

function backToInput() {
  stopAutoplay();
  slideshowSection.classList.add("hidden");
  inputSection.classList.remove("hidden");
}

// ─── UI Helpers ───────────────────────────────────────────────────────────
function setLoading(loading) {
  generateBtn.disabled         = loading;
  btnText.classList.toggle("hidden",   loading);
  btnLoader.classList.toggle("hidden", !loading);
}

function showError(msg) {
  errorMsg.textContent = `⚠ ${msg}`;
  errorMsg.classList.remove("hidden");
}

function hideError() {
  errorMsg.classList.add("hidden");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
