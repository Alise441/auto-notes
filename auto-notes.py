
import os, sys, subprocess, shutil, re
from pathlib import Path
from typing import Optional, List
import fitz  # PyMuPDF: PDF reading/writing and page compositing
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception_type
from openai import OpenAI

OA = OpenAI()  # OpenAI client (Responses API)

SYSTEM_PROMPT = """You are a teaching assistant that generates concise, well-structured annotations for lecture slides.
Use plain text plus LaTeX-style math delimiters ($...$ for inline, $$...$$ for display). No LaTeX packages, no environments.
Sections with exact headers and order, each 2-4 sentences:

Explanation: (Explain what the slide shows in simple, accessible language. Avoid jargon.)
Equation breakdown: (If there are formulas, rewrite them using LaTeX and explain every symbol and operation. Skip this section if no formulas appear.)
Intuition: (Explain the core idea — why it matters and how to think about it.)
Mental checkpoint: (Explain where we are in the lecture flow and how this connects to the broader topic.)
Connections: (Describe how this concept links to past or upcoming topics.)

Keep it compact and didactic.
"""

USER_PROMPT = """Course: {course_name}

Slide title (if any): {title}

Raw slide text:
{body}

Write only the annotation content with the exact section headers above, using $...$ or $$...$$ for math.
"""

# robust LLM call with retries on transient failures
@retry(wait=wait_exponential_jitter(initial=1, max=20),
       stop=stop_after_attempt(5),
       retry=retry_if_exception_type(Exception))
def call_gpt5(user_prompt: str, max_tokens: int = 2000) -> str:
    # compose a Responses API request with system+user prompts
    resp = OA.responses.create(
        model="gpt-5",
        input=[
            {"role":"system", "content": SYSTEM_PROMPT},
            {"role":"user", "content": user_prompt},
        ],
        reasoning={"effort":"low"},
        text={"verbosity":"medium"},
        max_output_tokens=max_tokens,
    )
    return (resp.output_text or "").strip()

def extract_text(page: fitz.Page) -> str:
    # primary text extraction preserving ligatures/whitespace
    t = page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE).strip()
    if not t:
        # fallback to block-level text if direct extraction is empty
        blocks = page.get_text("blocks")
        t = "\n".join(b[4] for b in blocks if isinstance(b[4], str)).strip()
    return t

def render_md_to_pdf(markdown: str, node_script: Path, notes_rect: fitz.Rect) -> bytes:
    # invoke the Node renderer (render/render-note.js) and return PDF bytes from stdout
    env = os.environ.copy()
    env["NOTE_WIDTH"] = str(int(notes_rect.width))
    env["NOTE_HEIGHT"] = str(int(notes_rect.height))
    p = subprocess.run(
        ["node", str(node_script)],
        input=markdown.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    if p.returncode != 0:
        # surface renderer errors to stderr for debugging
        sys.stderr.write(p.stderr.decode("utf-8", errors="ignore"))
        raise RuntimeError("render-note.js failed")
    return p.stdout  # PDF bytes

def parse_pages(spec: Optional[str], total: int) -> Optional[List[int]]:
    # parse page selection like "1,3-5" into a sorted unique list within [1, total]
    if not spec:
        return None
    sel = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            sel.extend(range(int(a), int(b)+1))
        else:
            sel.append(int(chunk))
    sel = [p for p in sel if 1 <= p <= total]
    return sorted(set(sel)) or None

def format_annotation_headers(body: str) -> str:
    # make annotation headers bold for Markdown rendering
    headers = [
        "Title:",
        "Explanation:",
        "Equation breakdown:",
        "Intuition:",
        "Mental checkpoint:",
        "Connections:",
    ]

    for h in headers:
        label = h.rstrip(":") # remove colon for formatting
        pattern = rf"(?m)^{re.escape(h)}" # match header at start of line
        replacement = f"**{label}:**\n"
        body = re.sub(pattern, replacement, body)

    return body


def annotate_pdf(
    input_pdf: Path,
    output_pdf: Path,
    course_name: str = "(unspecified)",
    node_script: Path = Path("render/render-note.js"),
    side: str = "right",
    margin_ratio: float = 1.0,
    pages: Optional[List[int]] = None,
    cache_root: Path = Path(".annot_cache"),
    force: bool = False
):
    # ensure Node.js is available for the Markdown→PDF rendering step
    if not shutil.which("node"):
        raise RuntimeError("Node.js not found. Install it first.")
    # open input and prepare an empty output PDF
    src = fitz.open(str(input_pdf))
    dst = fitz.open()

    # auto cache per document stem (stable, filesystem-friendly name)
    def _slug(s: str) -> str: # simple slugify
        return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

    # path to cache: cache_root/course_name/doc_stem/
    cache_dir = cache_root / f"{_slug(course_name)}/{Path(input_pdf).stem}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # default to all pages if no subset provided
    pages_iter = range(1, len(src)+1) if pages is None else pages

    for idx in pages_iter:
        # read source page and compute new canvas with a notes column
        page = src[idx-1]
        rect = page.rect
        note_w = rect.width * margin_ratio
        new_w, new_h = rect.width + note_w, rect.height
        new_page = dst.new_page(width=new_w, height=new_h)

        # place original slide and define the notes rectangle on the chosen side
        if side == "right":
            new_page.show_pdf_page(fitz.Rect(0,0,rect.width,rect.height), src, idx-1)
            notes_rect = fitz.Rect(rect.width, 0, new_w, new_h)
        else:
            new_page.show_pdf_page(fitz.Rect(note_w,0,new_w,rect.height), src, idx-1)
            notes_rect = fitz.Rect(0, 0, note_w, new_h)

        # cache per slide: markdown from LLM and rendered PDF fragment
        pdir = cache_dir / f"slide_{idx:03d}"
        pdir.mkdir(exist_ok=True)
        md_path  = pdir / "note.md"
        pdf_path = pdir / "note.pdf"

        if (not force) and md_path.exists():
            # use cached markdown to avoid re-calling the LLM
            note_md = md_path.read_text(encoding="utf-8")
        else:
            # generate new markdown via LLM using extracted slide text
            raw = extract_text(page)
            title = next((ln for ln in raw.splitlines() if ln.strip()), f"Slide {idx}")
            prompt = USER_PROMPT.format(
                    course_name=course_name[:120],
                    title=title[:120], 
                    body=raw if raw else "(no text detected)"
            )
            note_md = call_gpt5(prompt, max_tokens=2000)
            # normalize non-breaking spaces to regular spaces for consistent rendering
            note_md = note_md.replace("\u00A0", " ")
            # make annotation headers bold for Markdown rendering
            note_md = format_annotation_headers(note_md)
            md_path.write_text(note_md, encoding="utf-8")

        # render PDF fragment from Markdown (vector, via Node renderer)
        pdf_bytes = render_md_to_pdf(note_md, node_script, notes_rect)
        pdf_path.write_bytes(pdf_bytes)

        # insert vector PDF of notes into the destination page at notes_rect
        note_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            new_page.show_pdf_page(notes_rect, note_doc, 0, keep_proportion=False)
        finally:
            note_doc.close()

        print(f"[ok] page {idx}")

    # save output with compression and garbage collection
    dst.save(str(output_pdf), deflate=True, garbage=4)
    dst.close()
    src.close()
    print(f"✅ Saved → {output_pdf}")

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Annotate PDF with GPT-5 notes (Markdown+KaTeX→vector PDF) on the side.")
    ap.add_argument("input_pdf", type=Path)
    ap.add_argument("output_pdf", type=Path)
    ap.add_argument("--course_name", type=str, default="(unspecified)",
                help="Course name to tailor terminology (e.g., 'Reinforcement Learning').")
    ap.add_argument("--node_script", type=Path, default=Path("render/render-note.js"),
                help="Path to the Node.js script that renders Markdown to PDF.")
    ap.add_argument("--side", choices=["right","left"], default="right",
                    help="Side to place the notes column.")
    ap.add_argument("--margin_ratio", type=float, default=1.0,
                    help="Width of notes column as a fraction of slide width.")
    ap.add_argument("--pages", type=str, default=None,
                    help="Comma-separated list of pages or ranges to annotate (e.g., '1,3-5'). Default: all pages.")
    ap.add_argument("--cache_root", type=Path, default=Path(".annot_cache"),
                    help="Root directory for caching annotations.")
    ap.add_argument("--force", action="store_true",
                    help="Force requerying LLM and re-rendering all notes even if cached.")
    args = ap.parse_args()

    # determine total pages and resolve optional page selection
    total = fitz.open(str(args.input_pdf)).page_count
    pages = parse_pages(args.pages, total)

    annotate_pdf(
        input_pdf=args.input_pdf,
        output_pdf=args.output_pdf,
        course_name=args.course_name,
        node_script=args.node_script,
        side=args.side,
        margin_ratio=args.margin_ratio,
        pages=pages,
        cache_root=args.cache_root,
        force=args.force
    )

if __name__ == "__main__":
    main()
