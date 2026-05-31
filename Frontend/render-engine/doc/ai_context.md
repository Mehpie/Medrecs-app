# MedRecs Application - AI Context Document

## 1. Project Objective
MedRecs is a split-pane Legal/Medical Report Editor. The frontend takes a highly structured JSON payload representing a large document (100+ pages), renders it in a continuous A4-styled rich text editor on the left pane, and synchronizes citation clicks with a PDF viewer on the right pane.

## 2. Core Architectural Constraints
**IMPORTANT RULES FOR AI AGENTS WORKING ON THIS REPOSITORY:**
- **Do NOT use standard `contenteditable` divs.** Rich text rendering and editing MUST be handled exclusively by TipTap (ProseMirror).
- **Strict Data Contract:** The backend and frontend communicate via a rigid JSON format (The "God Payload"). You must use adapter functions (`src/utils/adapter.js`) to translate this JSON into TipTap's internal format, and vice-versa.
- **Performance:** Do not trigger full-app re-renders on keystrokes. Use Zustand for state to bypass React Context re-renders. Use debounced functions for autosaving (1500ms).
- **Split-Pane Sync:** The left pane (Editor) and right pane (PDF Viewer) are completely decoupled visually and communicate ONLY via the Zustand global state (`useReferenceStore.js`).

## 3. Technology Stack
- **Framework:** React / Next.js / Vite
- **Styling:** Tailwind CSS + custom CSS (`index.css`)
- **Editor Engine:** TipTap (Headless ProseMirror framework)
- **PDF Viewer:** `react-pdf` (with `pdfjs-dist` worker)
- **State Management:** Zustand
- **Icons:** Lucide React

## 4. Directory Structure
```text
src/
├── components/
│   ├── Editor/
│   │   ├── TipTapEditor.jsx          # Main Editor Entry Point
│   │   ├── EditorA4Container.jsx     # Visual A4 Paper Wrapper & Gutter Setup
│   │   └── extensions/               # Custom TipTap Node/Mark Extensions
│   │       ├── CitationNode.jsx      # Inline clickable superscripts (e.g. [1])
│   │       ├── BlockReference.js     # Block-level right-gutter citations
│   │       └── TocNode.jsx           # Table of Contents custom node
│   ├── PDFViewer/
│   │   ├── PDFViewer.jsx             # react-pdf implementation with highlighting
│   │   └── HighlightBox.jsx          # Overlay for bounding box highlighting
│   └── Layout/
│       └── SplitPane.jsx             # CSS Grid layout for Left/Right panes
├── store/
│   └── useReferenceStore.js          # Zustand store (activeReference state)
├── utils/
│   ├── adapter.js                    # Converts God Payload JSON <-> TipTap JSON
│   └── mockData.js                   # Mock "God Payload" for testing
├── App.jsx
├── main.jsx
└── index.css                         # Tailwind imports and TipTap CSS
```

## 5. The "God Payload" API Contract
The application revolves entirely around parsing and mutating this strict JSON schema.

### Root Level
```json
{
  "document_id": "string",
  "references": {
    "ref_1027": {
      "source_page": 55,
      "bounding_boxes": [[0.15, 0.4, 0.7, 0.45]]
    }
  },
  "blocks": [
    // Array of Block Objects...
  ]
}
```

### Content Blocks (`blocks` array)
All blocks require an `id`, `type`, and optionally `marginBottom`, `alignment`, and `refs` (for right-hand gutter badging).

1. **HEADING / PARAGRAPH:** Requires a `spans` array for inline formatting.
2. **LIST:** Requires `list_type` ("bullet" | "number") and an `items` array. Items contain `spans`, `level` (for nesting), and optionally `refs`.
3. **DIVIDER:** Simple horizontal rule (`thickness`, `color`).
4. **TOC:** Table of contents requiring an `entries` array (`title`, `page_number`, `level`).
5. **TABLE:** Requires a `rows` array. Each row has a `cells` array, containing `isHeader` (boolean) and `spans`. Optionally accepts `colwidth` per cell.

### Inline Text (`spans` array)
Used inside Headings, Paragraphs, and List Items to mix bold, italic, and inline citations seamlessly.
```json
{ 
  "text": "Mixed formatting text ", 
  "bold": true, 
  "italic": false,
  "refs": ["ref_1027"] // Renders via CitationNode as a clickable superscript
}
```

## 6. How Data Flows
1. **Ingestion:** Data arrives from the backend as the "God Payload".
2. **Translation:** `convertBackendToTipTap()` parses the blocks and converts them into TipTap `doc > content` arrays.
3. **Editing:** TipTap manages the DOM, applying custom extensions (like `CitationNode`) to the translated JSON.
4. **Interaction:** User clicks an inline citation `[1]`. `CitationNode` calls `setActiveReference('ref_1')` in Zustand.
5. **Sync:** `PDFViewer` listens to Zustand, automatically sets `pageNumber` to the reference's `source_page`, and renders `HighlightBox` using the `bounding_boxes`.
6. **Autosave:** A debounced function in `TipTapEditor` listens for keystroke pauses, retrieves `editor.getJSON()`, translates it back to the backend schema via `convertTipTapToBackend()`, and fires the PATCH request.
