# 🧠 AutoNotes

> **AutoNotes** automatically generates clear, structured side-notes for your lecture PDFs using GPT-5 and KaTeX.  
> It reads each slide, creates an explanation with equations and intuition, and produces an annotated PDF ready for GoodNotes or any note-taking app.

---

## ⚠️ Important note about GPT-5 usage

AutoNotes uses **OpenAI’s GPT-5 model** through the official API.  
Requests to GPT-5 are **paid** — each annotation consumes API tokens depending on slide length and model output.

- 🔗 Pricing: [https://openai.com/api/pricing](https://openai.com/api/pricing)  
- 🔑 To get an API key: create an account and generate it here — [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

---

## ✨ Features

- 🤖 **GPT-5–powered** — each slide is summarized and explained with correct math notation.  
- 📐 **KaTeX rendering** — beautiful, scalable equations.  
- 📄 **Vector PDF output** — annotations stay sharp and lightweight.  
- 💾 **Per-slide caching** — text is stored locally so you can re-render layout without new GPT calls.  
- ⚙️ **Flexible layout** — choose side, width, padding, and DPI.  
- 🎓 **Course-aware** — tailor terminology to your subject (e.g., *Reinforcement Learning*, *Machine Learning*, *Statistics*).

---

## 🚀 Quick start

### 1. Clone and install dependencies

```bash
git clone https://github.com/yourname/auto-notes.git
cd auto-notes

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Python packages
pip install -r requirements.txt

# Node packages for KaTeX renderer
npm init -y --prefix render
npm install --prefix render katex marked puppeteer
```

### 2. Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-..."
```

### 3. Generate annotated PDF

```bash
# Annotate pages 1–3 for a Reinforcement Learning lecture
python auto-notes.py RL_lecture.pdf RL_lecture_annotated.pdf \
    --course_name "Reinforcement Learning" \
    --pages 1-3
```

This reuses (if present) cached text (`.annot_cache_kx/reinforcement-learning/RL_lecture/slide_001-003/note.md`)  
and regenerates only the visual layout (no API cost).

### 4. Force requerying GPT5 and re-rendering all notes even if cached

```bash
python auto-notes.py RL_lecture.pdf RL_lecture_annotated.pdf \
    --course_name "Reinforcement Learning" \
    --force
```

---

## 🧩 Command-line options

| Argument | Type | Description |
|-----------|----------------|-------------|
| `input_pdf` | *path* | Path to original slides |
| `output_pdf` | *path* | Path to save annotated PDF |
| `--course` | string `(unspecified)` | Course name to adjust terminology |
| `--pages` | e.g. `1-3,5` (default = all) | Pages to annotate |
| `--side` | `right` / `left` | Where to place annotations |
| `--margin_ratio` | `0.5` | Width of annotation column (fraction of slide width) |
| `--force` | flag | Force requerying LLM and re-rendering all notes even if cached |
| `--note_pad` | `8` | Inner padding (px) in KaTeX render |
| `--note_dpr` | `2.0` | Device pixel ratio for Puppeteer (1–3) |

See full help with:
```bash
python auto-notes.py --help
```

---

## 🧩 Requirements

**Python ≥ 3.10**
- `pymupdf`
- `tenacity`
- `openai`

**Node.js ≥ 18**
- `puppeteer`
- `katex`
- `marked`

---

## 🧱 Project structure

```bash
auto-notes/
├── auto-notes.py           # Main Python script
├── requirements.txt
├── README.md
├── render/
│   ├── render-note.js        # Node.js KaTeX renderer
│   ├── package.json
│   └── node_modules/
└── .annot_cache/             # Auto-generated cache per input PDF
```

## 🧰 License

MIT License © 2025  
Feel free to fork and adapt for your own courses.

---

> Created by **Alina Ponomareva** at UZH —  
> built for clarity, math, and good notes ✨

