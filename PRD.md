# Product Requirements Document: Scenova

## 1. Executive Summary
**Scenova** is a GenAI-driven "Automated Visual Director" that transforms narrative text into high-fidelity, stylistically consistent storyboards. 

Unlike standard text-to-image generators that treat prompts as isolated entities, Scenova employs a sophisticated **9-stage pipeline** that ensures narrative continuity, character locking, and environment persistence. It is designed for filmmakers, advertisers, and creative directors who need to visualize pitches rapidly without sacrificing visual coherence.

---

## 2. Problem Statement
The current landscape of AI image generation (e.g., Midjourney, DALL-E) is optimized for single-image creation. When users attempt to visualize a sequential story, they face:
- **Narrative Drift**: Characters and environments change appearance between frames.
- **Workflow Friction**: Manually crafting consistent prompts for 5-10 scenes is time-consuming.
- **Lack of Narrative Context**: Image generators lack the "semantic memory" to understand that Scene 2 happens in the *same* room as Scene 1 but with a different light source.

---

## 3. Goals & Use Cases
### Goals
- **Maintain Visual Locking**: Ensure character identity and visual style are preserved across the storyboard.
- **Speed-to-Pitch**: Reduce the time to create a 4-panel storyboard from hours of manual prompting to <30 seconds.
- **Cinematic Quality**: Inject professional lighting, camera angles, and lens metadata automatically.

### Non-Goals
- **Video Generation** (v1 focus is purely static storyboarding).
- **Exact Vector Editing** (images are generated, not manually editable as layers).

---

## 4. User Personas
1. **The Creative Director**: Needs to quickly show a client the "vibe" of a 30-second commercial.
2. **The Indie Scriptwriter**: Wants to see their script come to life to identify pacing issues.
3. **The Marketing Manager**: Needs quick visuals for social media campaign narratives.

---

## 5. Functional Requirements

### 5.1 Narrative Processing
- **Input Parsing**: Support paragraph-based narrative inputs (3-5 sentences).
- **Automatic Segmentation**: AI must break long text into logical "narrative beats" (Scenes).

### 5.2 Contextual Intelligence (The "Context Lock")
- **Global Context Extraction**: Identify "The Hero" (physical traits) and "The World" (setting/lighting) before generating any images.
- **Scene Enrichment**: Each scene's prompt must be a merge of `Global Features` + `Scene-Specific Action`.

### 5.3 Visual Quality & Control
- **Style Presets**: Users can choose from *Cinematic*, *Anime*, *Realistic*, or *Concept Sketch*.
- **Aspect Ratio Control**: Default to cinematic wide (16:9).

### 5.4 Output & Export
- **Storyboard View**: A sleek, full-screen grid showing images alongside narrative captions.
- **Exporting (Roadmap)**: PDF or Image-Strip export for pitch decks.

---

## 6. Technical Architecture (The 9-Step Pipeline)

Scenova operates on a decoupled architecture (FastAPI + Vanilla JS) using an asynchronous orchestrator:

| Stage | Name | Action | Logic |
| :--- | :--- | :--- | :--- |
| **1** | **Segmentation** | Groq LLaMA 3 | Breaks text into discrete narrative beats. |
| **2** | **Identity Mapping** | Groq LLaMA 3 | Extracts "Global Context" (Character visual attributes). |
| **3** | **Feature Extraction** | Internal Logic | Assigns tone, emotion, and environment to each beat. |
| **4** | **Prompt Enrichment** | Groq | Merges Identity + Beat to create a "Technical Director's Prompt." |
| **5** | **Style Injection** | Internal Logic | Adds lighting (e.g., "Volumetric lighting") and lens (e.g., "35mm anamorphic"). |
| **6** | **Parallel Gen** | MiniMax/HF | Executes N image generation calls concurrently using `asyncio.gather`. |
| **7** | **Storage/Caching** | Cloudinary | Uploads generated assets for high-speed delivery. |
| **8** | **Validation** | Pydantic | Ensures image integrity and minimum panel count (≥ 3). |
| **9** | **UI Rendering** | Vanilla JS | Reconstructs the story in a responsive grid. |

---

## 7. UX & Design Principles
- **"One-Click Visuals"**: The user provides text; the machine provides the direction.
- **Aesthetic Excellence**: Use dark mode, glassmorphism, and minimal distractions to keep the focus on the art.
- **Wait-Time Feedback**: Clear progress indicators for the multi-stage pipeline.

---

## 8. Success Metrics (KPIs)
- **Generation Speed**: Average E2E pipeline completion in under 25 seconds.
- **Consistency Score**: Human-eval check for character/setting retention across panels (>80% success).
- **Completion Rate**: % of generations that successfully yield ≥ 3 panels without API failure.

---

## 9. Future Roadmap
- **Character Reference Images**: Allow users to upload a photo of a character to "lock" identity.
- **Voice-over Integration**: Generate a narrative audio pass for the storyboard.
- **Interactive Editing**: Regenerate specific panels with "tweak" instructions.
- **Collaboration**: Sharing links for storyboard review.
