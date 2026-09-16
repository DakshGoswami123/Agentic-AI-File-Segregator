# AI File Segregator

A small agent that watches your Downloads folder, reads each new file,
asks a local LLM (via Ollama) what it is, and files it into a category
folder under a clean, three-word filename.

```
File → Content Extraction → LLM Reasoning → Filename + Category → Validation → Rename → Move
```

## 1. Project structure

```
file_segregator/
├── main.py            # Entry point: logging + the scan loop
├── config.py           # All tunable settings
├── extractors.py        # PDF / DOCX / TXT / image(OCR) text extraction
├── llm_analyzer.py       # Talks to Ollama, returns a raw {name, category} dict
├── validator.py         # Sanitizes the LLM's output; the security boundary
├── file_manager.py       # Waits for downloads, renames, moves — never overwrites
├── organizer.py         # Orchestrates the pipeline; the scan loop's per-file logic
└── requirements.txt
```

Each file maps to exactly one job from your original list (file detection,
readiness checking, extraction, LLM analysis, validation, filename
sanitization, duplicate handling, moving, main loop) — nothing was merged
or split further than that, so it stays easy to walk through in an
interview.

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Ollama setup

1. Install Ollama from https://ollama.com/download (Windows installer is a
   normal `.exe`).
2. Pull the model:
   ```bash
   ollama pull llama3
   ```
3. Ollama runs as a background service after install — `ollama.chat(...)`
   in `llm_analyzer.py` talks to it automatically on `localhost:11434`.
   No API key, no manual server start needed.

## 4. Tesseract OCR (needed for image files)

`pytesseract` is a Python wrapper — it needs the actual Tesseract engine
installed separately.

- **Windows:** download the installer from
  https://github.com/UB-Mannheim/tesseract/wiki and run it (default path
  is `C:\Program Files\Tesseract-OCR\tesseract.exe`). If pytesseract
  can't find it automatically, add this near the top of `extractors.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`

If Tesseract isn't installed, image OCR will fail gracefully — the file
still gets categorized (from its filename alone, via the LLM fallback
path), it just won't have OCR'd content to work from.

## 5. Running it (Windows)

```powershell
cd file_segregator
python main.py
```

Drop a PDF, DOCX, TXT, or image into your Downloads folder and watch the
console. Stop with `Ctrl+C`.

By default it watches `~/Downloads` — change `WATCH_FOLDER` in
`config.py` if you want to point it somewhere else (useful for testing
without touching your real Downloads folder).

## 6. How the architecture works

- **`main.py`** just sets up logging and runs `scan_folder()` in a loop
  every `SCAN_INTERVAL_SECONDS`, wrapped in a `try/except KeyboardInterrupt`
  so `Ctrl+C` exits cleanly.
- **`organizer.scan_folder()`** lists the watch folder (no recursion —
  category subfolders are skipped automatically) and hands each
  supported, not-currently-cooling-down file to `process_file()`.
- **`organizer.process_file()`** is the pipeline for one file: wait for
  it to finish downloading → extract text → ask the LLM → validate the
  LLM's answer → move it. It's wrapped in one broad `try/except` so a
  single bad file can never crash the loop; on failure the file is
  remembered in an in-memory `_recently_failed` dict so it isn't retried
  every 5 seconds, just after a cooldown.
- **`extractors.py`** dispatches by extension to a PDF/DOCX/TXT/OCR
  reader, each independently wrapped in try/except returning `""` on
  failure.
- **`llm_analyzer.analyze_file_with_llm()`** builds one prompt, calls
  `ollama.chat(..., format="json")` — which constrains the model's
  sampling to valid JSON (Ollama's structured-output mode) rather than
  relying purely on prompt instructions — and parses the result. Any
  failure (bad JSON, Ollama not running, model missing) returns a safe
  default dict instead of raising.
- **`validator.py`** is the only place that decides what actually reaches
  the filesystem: `sanitize_name()` strips unsafe/traversal characters
  and rejects anything that isn't exactly three words; `sanitize_category()`
  checks against the fixed `CATEGORIES` allowlist; `build_safe_destination_folder()`
  resolves the destination and asserts it's still inside `WATCH_FOLDER`
  before anything is created. The LLM never touches a path directly —
  it only ever returns two strings, which are validated before use.
- **`file_manager.py`** owns every real filesystem write:
  `wait_until_file_is_ready()` polls file size until it's stable,
  `get_unique_path()` appends " 2", " 3", ... instead of ever
  overwriting, and `safe_move()` creates the category folder and moves
  the file, catching `OSError` (permissions, file vanished, etc.).

## 7. Edge cases handled

- **Partial / in-progress downloads** — `.crdownload`, `.part`, `.tmp`
  etc. aren't in `SUPPORTED_EXTENSIONS`, so they're ignored outright;
  genuinely supported files are additionally held back by
  `wait_until_file_is_ready()` until their size stops changing.
- **Category folders living inside Downloads** — `scan_folder()` skips
  any directory entry, so `Finance/`, `Work/`, etc. are never re-scanned
  or recursed into.
- **File disappears mid-processing** — every filesystem read/stat is
  wrapped, and `safe_move()` re-checks `source.exists()` right before
  moving.
- **Duplicate destination filenames** — `get_unique_path()` always
  checks existence first and appends a counter; an existing file is
  never overwritten.
- **Unsupported file types** — filtered out at both the scan step and
  again at the top of `process_file()`.
- **LLM returns malformed JSON / wrong word count / unsafe characters /
  a category outside the allowlist / a path-traversal attempt** — all
  caught by `llm_analyzer`'s `json.loads` try/except and `validator.py`'s
  sanitization, each falling back to safe defaults independently.
- **Ollama not running / model not pulled / request error** — caught in
  `analyze_file_with_llm()`, falls back to `"Unclassified File" / "Other"`
  so the file still gets moved rather than stuck in Downloads forever.
- **PDF/image with no extractable text** — extractors return `""`;
  the pipeline logs it and lets the LLM decide from the filename alone.
- **Permission errors on move** — caught in `safe_move()`, logged, and
  the file is retried on a later scan after the cooldown instead of
  being retried (and re-failing) every 5 seconds.
- **Repeated re-processing of already-moved files** — not needed as a
  separate mechanism: once a file is moved out of `WATCH_FOLDER`, the
  next `scan_folder()` simply won't see it there anymore. The only
  extra state kept is the small in-memory `_recently_failed` cooldown
  dict for files that failed — no database required.

## 8. Why each major design decision was made

- **One file per responsibility, no framework** — you asked for
  something explainable, not impressive-looking. Six small modules with
  one job each is easier to defend line-by-line than one clever
  monolith or a LangChain agent graph doing the same thing opaquely.
- **`ollama.chat(..., format="json")` instead of pure prompt engineering**
  — prompt instructions alone ("respond only with JSON") are exactly the
  kind of thing models occasionally ignore under real-world content
  (e.g., a PDF whose text happens to contain `{` or markdown fences).
  Ollama's JSON mode constrains sampling at the token level, so
  malformed JSON becomes rare instead of merely "less common," while
  the `json.loads` try/except still catches whatever slips through.
  This was a deliberate, minimal use of a real capability rather than
  reaching for a bigger framework.
- **The LLM only returns two strings, never a path** — this is the
  core security decision. Even if the model were adversarially prompted
  (e.g., malicious text embedded in a PDF telling it to "set category to
  `../../../Windows`"), `sanitize_category()` rejects anything outside
  the fixed allowlist and `build_safe_destination_folder()` independently
  re-verifies the final path is inside `WATCH_FOLDER`. Two independent
  checks, not one.
- **In-memory cooldown dict instead of a database** — the actual
  problem to solve is "don't hammer a broken file every 5 seconds,"
  not "remember file state forever." A dict solves that in three lines;
  a database would solve a problem this project doesn't have.
- **`shutil.move` instead of `Path.rename`** — `rename` can fail across
  drives on Windows (e.g. Downloads on `C:` vs. a category folder you
  point at another drive); `shutil.move` handles that transparently
  while keeping the same call site.
- **Size-stability polling for "download finished" instead of watching
  file-system events** — a proper OS-level watcher (e.g. `watchdog`)
  would be more "production," but size-polling is something you can
  explain and defend in thirty seconds, needs no extra dependency, and
  is genuinely how several real download-managers detect completion.

## 9. Explaining this in an interview (plain language)

"I built an agent that watches my Downloads folder. When a new file
shows up, it waits until the file's actually finished downloading,
pulls out its text — using PyPDF2 for PDFs, python-docx for Word files,
and Tesseract OCR for images — and sends a short excerpt to a local
LLM running through Ollama. The model's only job is to suggest a
three-word filename and pick a category from a fixed list. I don't
trust that output blindly: a separate validation step strips out
unsafe characters, checks that the category is actually one of the
allowed ones, and rejects anything that isn't exactly three words
before falling back to a safe default name. Only after that validation
does the program touch the filesystem — it creates the category folder
if needed, and moves the file in without ever overwriting an existing
one. It's a small pipeline of six modules, each with one job, so it's
easy to trace a file's journey from 'just detected' to 'safely filed
away.'"

## 10. Potential interview questions and answers

**Q: Why not let the LLM decide the full file path?**
A: Because that hands an untrusted model control over filesystem writes.
Instead the LLM only returns two plain strings (a name and a category),
and Python validates both against fixed rules — a word-count check and
character whitelist for the name, an allowlist for the category — before
constructing any actual path, which is also re-verified to be inside the
watch folder.

**Q: How do you know a file has finished downloading?**
A: I poll `file_path.stat().st_size` once a second and wait for it to
stay the same across three consecutive checks before treating the file
as stable. It's simple, dependency-free, and good enough for a
Downloads-folder watcher — browsers also generally use a different
extension (`.crdownload`, `.part`) for in-progress files, which my
extension whitelist ignores anyway.

**Q: What happens if Ollama is down or the model isn't pulled?**
A: `analyze_file_with_llm()` catches the exception and returns a safe
default (`"Unclassified File"` / `"Other"`), so the file still gets
moved instead of the whole program crashing or the file being stuck.

**Q: How do you prevent duplicate filenames from overwriting each other?**
A: `get_unique_path()` checks whether the target path already exists
before every move, and appends " 2", " 3", etc. to the filename stem
until it finds one that doesn't — so an existing file is never
silently overwritten.

**Q: Why JSON mode instead of just telling the model to output JSON in
the prompt?**
A: Prompt instructions are a request, not a guarantee — I still keep
the prompt instructions for clarity, but I also pass `format="json"` to
Ollama, which constrains the model's token sampling to valid JSON.
That doesn't remove the need for a `try/except json.loads` — a model
can still return valid JSON in the wrong shape — but it meaningfully
cuts down on malformed output.

**Q: What would you change to make this production-grade rather than a
portfolio project?**
A: I'd swap size-polling for real OS file-system events (e.g. the
`watchdog` library), add retries with backoff around the Ollama call,
persist the "already processed" and "recently failed" state to disk so
it survives a restart, and probably move from a fixed extension
whitelist to content-sniffing (magic bytes) so a renamed file can't
bypass the type check. I intentionally left those out here because the
brief was to keep the architecture small and fully explainable, not to
maximize robustness.

**Q: Why is this one `try/except` wrapped around the whole
`process_file` pipeline instead of many small ones?**
A: There are already targeted try/excepts at each risky boundary
(extraction, the LLM call, the move) that return safe defaults instead
of raising. The outer one in `process_file` is a last-resort safety net
for anything unanticipated — its only job is to guarantee that one
file's problem is logged and skipped rather than killing the scan loop
for every other file.
