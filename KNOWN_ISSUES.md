# DocMorph Known Issues & Edge Cases

Documented known issues, workarounds, and engineering edge cases in DocMorph.

---

## 1. Environment & Development Tooling

### Windows Smart App Control (SAC) / Application Control Policy
- **Symptom:** Antigravity IDE / VS Code terminal fails to launch with:
  `The terminal process failed to launch: A native exception occurred during launch (An Application Control policy has blocked this file ... conpty.node / pty.node)`
- **Root Cause:** Both `conpty.node` and fallback `pty.node` in `node_modules/node-pty/build/Release/` are native compiled C++ `.dll` files. Windows 11 Smart App Control (SAC) blocks unrecognized native binary `.node` files located in user AppData. Unchecking `windowsEnableConpty` simply causes the IDE to try `pty.node`, which is blocked by the exact same policy.
- **Resolution:**
  1. Open Windows Start Menu -> **Windows Security**.
  2. Go to **App & browser control** -> **Smart App Control settings**.
  3. Turn Smart App Control **Off** (standard procedure for developer environments on Windows 11).
  4. In Antigravity IDE Settings (`Ctrl + ,`), re-enable `windowsEnableConpty` for optimal terminal performance.

---

## 2. Document Processing & Detection Edge Cases

### Highly Degraded / Low-DPI Scanned PDFs
- **Symptom:** Scanned practical PDFs with photocopy artifacts, skew $> 15^\circ$, or low resolution ($< 150\,\text{DPI}$) may cause local Tesseract / ML Kit OCR to produce incomplete or fragmented character recognition for numeric enrollment numbers.
- **Handling:** DocMorph's Phase B/C engine classifies these pages as `FOOTER_UNCERTAIN` or `DOCUMENT_UNREADABLE`. The engine never guesses or hallucinates missing digits; it presents the candidate to the user with a warning badge for manual confirmation before replacement.

### Multi-Column Academic Layouts
- **Symptom:** Two-column research papers (e.g. IEEE format) may have trailing author affiliations or footnote text in the left column near the bottom.
- **Handling:** Position-aware layout filters check for vector separator rules and academic stop words ("affiliations", "university", "department", "index terms"). Footnotes without student identifiers are rejected from replacement.

### Rotated PDF Pages ($90^\circ$, $270^\circ$)
- **Symptom:** Documents where individual pages contain a `/Rotate` PDF dictionary flag.
- **Handling:** PDFBox and PyMuPDF normalize coordinates to the page cropbox matrix. However, bounding boxes rendered in manual selection must align with the rotated display matrix.

---

## 3. Personalization & Content Stream Rewriting

### Non-Standard or Embedded Subset Fonts
- **Symptom:** PDFs where custom or proprietary fonts are embedded as subsets without a standard Unicode mapping table (`/ToUnicode` CMap missing).
- **Handling:** `TypographyFormatter.kt` and `ContentStreamRedactor.kt` fall back to standard PDF typefaces (`Helvetica`, `Times-Roman`) with matched font size and baseline vertical positioning, preserving the visual layout without corrupting stream operators.
