# BookRevive 📖

**Turn photos of old books into polished EPUB files — entirely on your own machine.**

BookRevive is an open-source digitization pipeline that takes phone photos of book pages and converts them into clean, readable EPUB ebooks. No cloud upload required. No subscription. Everything runs locally.

---

## How It Works

```
Phone photos → image quality check → preprocess (deskew / denoise / binarise)
             → OCR (Tesseract) → AI fallback for difficult pages (optional)
             → text cleanup (ligatures, hyphenation, spell check)
             → chapter & heading detection → Markdown
             → Calibre → EPUB
```

---

## Features

- **Two interfaces** — a CLI for power users and a drag-and-drop web UI for everyone else
- **Smart OCR pipeline** — Tesseract runs first (fast, free, local). On low-confidence pages, Claude AI vision kicks in as a fallback for difficult or damaged text
- **Image preprocessing** — deskew, CLAHE contrast enhancement, denoising, and binarization before any OCR runs
- **Text cleanup** — fixes ligatures, broken hyphenation, and spell-check errors automatically
- **Chapter detection** — heading and chapter structure is detected and preserved in the output
- **One-click EPUB** — final output is a properly formatted EPUB with metadata (title, author, language)
- **Phone testing** — built-in network launcher lets you open the web UI on your phone over WiFi
- **Folder watch mode** — drop images into a folder and BookRevive processes them automatically

---

## Requirements

**Python dependencies** (installed via pip):
```
pytesseract, Pillow, opencv-python-headless, numpy, anthropic,
typer, rich, pyspellchecker, markdown, watchdog, streamlit
```

**System binaries** (installed separately):

| Tool | Purpose | Install |
|---|---|---|
| Tesseract | Local OCR engine | `sudo apt install tesseract-ocr tesseract-ocr-eng` (Linux) / `brew install tesseract` (macOS) |
| Calibre | EPUB generation | [calibre-ebook.com/download](https://calibre-ebook.com/download) |

**Optional:**
- `ANTHROPIC_API_KEY` — enables Claude vision fallback for low-quality or damaged pages

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOURUSERNAME/bookrevive.git
cd bookrevive

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Tesseract (Linux)
sudo apt install tesseract-ocr tesseract-ocr-eng

# 5. Install Calibre (Linux)
wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin

# 6. (Optional) Add your Anthropic API key for AI fallback
cp .env.example .env
# Edit .env and add your key

# 7. Verify everything is working
python main.py test
```

---

## Usage

### Web UI (recommended)

```bash
# Localhost only
bash run_web.sh

# Open on your phone over WiFi
bash run_web_network.sh
```

Then open `http://localhost:8501` in your browser — or the IP address printed in the terminal on your phone.

### CLI

```bash
# Process a folder of scanned pages
python main.py process scans/ --title "Oliver Twist" --author "Charles Dickens"

# Watch a folder and process automatically as images are added
python main.py watch scans/

# Run environment check
python main.py test
```

---

## Environment Variables

Create a `.env` file in the project root (see `.env.example`):

```bash
# Optional — enables Claude AI vision fallback for difficult pages
ANTHROPIC_API_KEY=your-key-here

# Optional — override Calibre location if not auto-detected
CALIBRE_BIN=/path/to/ebook-convert
```

Calibre is auto-detected in these locations in order:
`$CALIBRE_BIN` → PATH → `~/calibre-bin/` → `~/.local/bin/` → `/opt/calibre/` → `/usr/local/bin/` → macOS app bundle

---

## Project Structure

```
bookrevive/
├── main.py                  ← CLI entry point (Typer + Rich)
├── app.py                   ← Streamlit web UI
├── requirements.txt
├── .env.example
├── run_bookrevive.sh        ← CLI launcher
├── run_web.sh               ← Web UI launcher (localhost)
├── run_web_network.sh       ← Web UI launcher (phone/network)
├── core/
│   ├── ocr.py               ← Tesseract + Claude vision pipeline
│   ├── cleanup.py           ← ligature fix, hyphenation, spell check
│   ├── merger.py            ← page merge + chapter/heading detection
│   └── epub.py              ← Calibre EPUB wrapper
└── utils/
    ├── image_prep.py        ← deskew, CLAHE, denoise, quality check
    ├── watcher.py           ← folder monitor
    └── editor.py            ← open file in $EDITOR
```

---

## Tips for Best Results

- Shoot pages in **good natural light** — avoid shadows across the text
- Keep the camera **parallel to the page** — angled shots reduce OCR accuracy
- **Higher resolution is better** — the preprocessing pipeline handles the rest
- If a page comes out poorly, retake the photo and reprocess just that page
- Enable the Claude vision fallback (`ANTHROPIC_API_KEY`) for old, faded, or damaged text

---

## License

MIT License — free to use, modify, and distribute.

---

## Contributing

Pull requests welcome. If you find a bug or want to request a feature, open an issue.
