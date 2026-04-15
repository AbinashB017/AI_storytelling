# Scenova — Cinematic Visual Director

[![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20%2F%20LLaMA3-orange)](https://groq.com)
[![MiniMax](https://img.shields.io/badge/ImageGen-MiniMax-blue)](https://minimaxi.com)
[![Cloudinary](https://img.shields.io/badge/Storage-Cloudinary-blueviolet)](https://cloudinary.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Scenova** is a production-grade, AI-powered **Cinematic Visual Director** that transforms a short narrative paragraph into a visually coherent, multi-panel storyboard. The system combines deep LLM reasoning (Groq/LLaMA) with high-fidelity image generation (MiniMax) and persistent cloud storage (Cloudinary) to deliver a professional-grade editorial experience.

The frontend is a fully redesigned, **glassmorphic dark/light mode UI** built with Tailwind CSS and a custom "Anamorphic Frame" design system — inspired by professional film editing suites.

---

## 🎯 What It Does

Give Scenova a story in 3–5 sentences. It returns a full, visually consistent storyboard with:
- AI-generated scene images per panel
- Cinematic headlines and captions per scene
- Narrative role tags (e.g., Master Shot, Rising Action, Resolution)
- Downloadable HTML storyboard artifact

---

## ✨ What's New (Latest Update)

### 🎨 Full UI Overhaul — "Anamorphic Frame" Design System
- **Glassmorphic Purple/Violet Theme:** Deep obsidian backgrounds with electric violet (`#7c5cff`) accents and `backdrop-blur` glass cards.
- **Sidebar Navigation:** Clean permanent sidebar with "Scenova AI" module label — Timeline and Moodboard removed for focused UX.
- **Dark / Light Mode Toggle:** A premium pill toggle in the top navigation bar. Light mode uses a warm lavender/parchment palette (`#f0ebff`) — not plain white — with full text contrast enforcement.
- **Aligned Input Grid:** "Narrative Context" textarea and controls (Visual Aesthetic dropdown + Generate Storyboard button) are now perfectly height-aligned in a 12-column grid.
- **Cinematic Slideshow (21:9):** Widescreen aspect-ratio slide viewer with glassmorphic prev/next controls, scene counter badge, dot-row navigator.
- **Grid View:** Grayscale-to-color hover reveals with scene badges.
- **Loading Overlay:** Animated central orb with pulsing ring and step-by-step pipeline progress.
- **No backend changes** — all UI work is strictly frontend.

### 🧠 Engine Labeling Update
- Engine footer updated to accurately reflect: **Groq · MiniMax · Cloudinary**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  SCENOVA FRONTEND                     │
│  (Tailwind CSS / Vanilla JS / Glassmorphic Dark UI)   │
│  - Visual Director Input                              │
│  - Cinematic Slideshow + Grid View                    │
│  - Dark / Light Mode Toggle                           │
└───────────────────────┬─────────────────────────────┘
                        │ POST /api/v1/generate-storyboard
                        ▼
┌─────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (Uvicorn)                │
│  src/app/main.py → endpoints/storyboard.py            │
└──────────────────┬────────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   9-STEP PIPELINE   │
         └─────────────────────┘
         │
         ├─ Step 1: Global Context Extraction   ──► Groq (LLaMA 3)
         ├─ Step 2: Scene Segmentation           ──► Groq (LLaMA 3)
         ├─ Step 3: Narrative Role Assignment    ──► Groq (LLaMA 3)
         ├─ Step 4: Scene Feature Extraction     ──► Groq (LLaMA 3)
         ├─ Step 5: Scene Enrichment             ──► Groq (LLaMA 3)
         ├─ Step 6: Cinematic Prompt Engineering ──► Groq (LLaMA 3)
         ├─ Step 7: Headline + Caption Gen       ──► Groq (LLaMA 3)
         ├─ Step 8: Parallel Image Generation    ──► MiniMax API
         └─ Step 9: Cloud Upload + URL Return    ──► Cloudinary
```

### Architecture Decision Record
| Component | Technology | Reason |
|-----------|-----------|--------|
| Web Framework | FastAPI | Async-first, automatic OpenAPI docs, Pydantic validation |
| LLM | Groq (LLaMA 3) | Sub-second inference, multi-key round-robin load balancing |
| Image Gen | MiniMax | High-fidelity cinematic image generation API |
| Storage | Cloudinary | Persistent image hosting + CDN delivery |
| Frontend | Tailwind CSS + Vanilla JS | Zero-dependency, premium design control |
| Concurrency | asyncio.gather | Parallel scene generation cuts latency by ~60% |

---

## ⚙️ Tech Stack

### Backend
- **Python 3.10+**
- **FastAPI** — High-performance async web framework
- **AsyncIO + HTTPX** — Non-blocking parallel API calls
- **Pydantic v2** — Request/response schema validation
- **python-dotenv** — Secure environment variable management

### AI Engine
- **Groq Cloud** — LLaMA 3 for all 7 LLM pipeline steps
- **Multi-key Round-Robin** — Load balancing across multiple Groq API keys
- **MiniMax** — Primary image generation model

### Storage & CDN
- **Cloudinary** — Image upload, persistent URL hosting, CDN delivery
- **Local Fallback** — `static/` directory for development

### Frontend
- **Tailwind CSS (CDN)** — Utility-first styling with custom design tokens
- **Space Grotesk + Inter** — Premium Google Fonts typography
- **Material Symbols** — Icon system
- **Vanilla JavaScript** — State management, DOM control, API integration

---

## 🔄 The 9-Step Pipeline

```
Narrative Text
      │
      ▼
[1] Global Context Extraction
      Extract: main_character, character_appearance, clothing,
               character_identity, environment, tone, visual_style
      │
      ▼
[2] Scene Segmentation
      Split into 3–5 discrete narrative beats (scenes)
      │
      ▼
[3] Narrative Role Assignment
      Tag each scene: master_shot / rising_action / climax /
                      resolution / epilogue / ...
      │
      ▼
[4] Scene Feature Extraction (parallel)
      Per scene: emotion, tone, environment
      │
      ▼
[5] Scene Enrichment (parallel)
      Merge scene features + global context → enriched_description
      │
      ▼
[6] Cinematic Prompt Engineering
      Convert to technical image gen prompt with:
      - Character appearance/clothing lock
      - Lighting + lens directives
      - Style token injection
      │
      ▼
[7] Headline + Caption Generation
      Short cinematic headline + narrative caption per scene
      │
      ▼
[8] Parallel Image Generation
      asyncio.gather → MiniMax API for all scenes simultaneously
      │
      ▼
[9] Cloud Upload
      Each image → Cloudinary → persistent URL
      │
      ▼
StoryboardResponse { panels: [...], total_scenes: N }
```

---

## 🎨 Frontend Features

| Feature | Description |
|---------|-------------|
| **Dark Mode** | Deep obsidian purple (`#0b0814`) with violet (`#7c5cff`) accents |
| **Light Mode** | Warm lavender/parchment (`#f0ebff`) — premium, not plain white |
| **Theme Toggle** | Pill-shaped toggle in top navbar, smooth 300ms transition |
| **Slideshow View** | 21:9 cinematic widescreen with hover controls + dot navigator |
| **Grid View** | 4-column panel overview with grayscale-to-color hover reveal |
| **Autoplay** | Configurable 4s interval, Space bar toggle, looping |
| **Keyboard Nav** | Arrow keys for slide navigation, Escape to exit |
| **Loading Overlay** | Glassmorphic overlay with animated orb + 5-step progress |
| **HTML Export** | Downloads a standalone storyboard HTML file with embedded styles |
| **Character Counter** | Live counter (max 2000 chars) |
| **Error Display** | Inline glass-card error panel for API or validation errors |

---

## 🚀 Getting Started

### Prerequisites
```
Python 3.10+
pip
Groq API Key(s)
MiniMax API Key + Group ID
Cloudinary Account (cloud name, API key, secret)
```

### 1. Clone the Repository
```bash
git clone https://github.com/AbinashB017/AI_storytelling.git
cd AI_storytelling
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file in the root directory:
```env
# Groq — supports comma-separated keys for load balancing
GROQ_API_KEYS=your_groq_key_1,your_groq_key_2

# MiniMax
MINIMAX_API_KEY=your_minimax_key
MINIMAX_GROUP_ID=your_group_id

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 4. Run the Application
```bash
$env:PYTHONPATH="src"          # Windows PowerShell
uvicorn app.main:app --reload --port 8000
```

### 5. Open the UI
Navigate to: **http://localhost:8000/static/index.html**

---

## 📁 Project Structure

```
AI_storytelling/
├── src/
│   └── app/
│       ├── main.py                    # FastAPI app + CORS + static mount
│       ├── endpoints/
│       │   └── storyboard.py          # POST /api/v1/generate-storyboard
│       ├── models/
│       │   └── schemas.py             # Pydantic schemas (request/response)
│       └── services/
│           ├── pipeline.py            # 9-step orchestration pipeline
│           ├── groq_client.py         # Groq multi-key client w/ round-robin
│           ├── image_generator.py     # MiniMax image generation
│           ├── cloudinary_service.py  # Cloudinary upload service
│           └── local_storage_service.py # Local image fallback
├── frontend/
│   ├── index.html                     # Main UI (Tailwind + custom design system)
│   ├── app.js                         # Frontend logic (state, API, DOM)
│   └── style.css                      # Glassmorphic design + light/dark modes
├── static/                            # Served by FastAPI StaticFiles
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── *.png                          # Locally stored scene images (fallback)
├── PRD.md                             # Product Requirements Document
├── requirements.txt
└── README.md
```

---

## 📡 API Reference

### `POST /api/v1/generate-storyboard`

**Request Body:**
```json
{
  "text": "A young engineer discovers a hidden talent for painting after losing his job...",
  "style": "cinematic"
}
```

**Response:**
```json
{
  "panels": [
    {
      "scene_id": 1,
      "image_url": "https://res.cloudinary.com/.../scene_1.png",
      "headline": "The Last Dashboard",
      "caption": "A young engineer clears his desk under the cold glow of monitors.",
      "narrative_role": "master_shot"
    }
  ],
  "total_scenes": 4
}
```

**Available Styles:** `cinematic` · `realistic` · `anime` · `oil painting` · `sketch`

**Interactive Docs:** http://localhost:8000/docs

---

## ⚡ Performance

- **Parallel Generation:** `asyncio.gather` across all scenes → ~60% faster than sequential
- **Multi-Key Groq:** Round-robin load balancing prevents rate-limit throttling
- **Cloudinary CDN:** Generated images served globally via CDN after upload

---

## 🛣️ Roadmap

- [ ] **LoRA Character Embeddings** — Exact character face/appearance persistence
- [ ] **Video Animatic Export** — Extend storyboard into a short MP4 animatic
- [ ] **Prompt Version History** — Save and reload past generations
- [ ] **Style Presets Gallery** — Visual preset picker (noir, dreamlike, etc.)
- [ ] **Multi-language Input** — Accept narratives in non-English languages

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Built with ♦ by Abinash** — *Transforming narratives into cinematic visual stories.*
