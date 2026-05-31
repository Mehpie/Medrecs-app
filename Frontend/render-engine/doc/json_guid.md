# JSON Payload Guide (`godPayload`)

This document outlines the schema of the `godPayload` object that the backend should provide to the rendering engine. The TipTap editor uses an adapter (`src/utils/adapter.js`) to parse this JSON and render it perfectly into paginated A4 pages.

## Root Object

```json
{
  "document_id": "string",
  "metadata": {
    "page_number": 77,
    "total_pages": 92,
    "start_line_number": 2127
  },
  "references": {
    "ref_1": {
      "source_page": 2,
      "bounding_boxes": [[0.1, 0.08, 0.85, 0.18]]
    }
  },
  "blocks": [
    // Array of block objects
  ]
}
```

## Universal Block Attributes

All items in the `blocks` array share these base attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `string` | Unique identifier for the block (e.g., `"blk_123"`). |
| `type` | `string` | The block type (see below for specific types). |
| `alignment` | `string` | Text alignment: `"left"`, `"center"`, `"right"`, or `"justify"`. |
| `marginBottom` | `string` | CSS margin string (e.g., `"16px"`, `"1px"`). Controls precise spacing. |
| `line_number` | `integer` | (Optional) Explicitly overrides the line number shown in the left gutter. |
| `refs` | `array[string]` | (Optional) Array of reference IDs attached to the whole block. |

---

## Block Types

### 1. `PARAGRAPH`
Standard text block.
```json
{
  "id": "blk_1",
  "type": "PARAGRAPH",
  "alignment": "left",
  "marginBottom": "24px",
  "spans": [
    // Array of Span Objects (see Spans section)
  ]
}
```

### 2. `HEADING`
Header text.
```json
{
  "id": "blk_2",
  "type": "HEADING",
  "level": 2, // Integer 1-6 (h1 to h6)
  "alignment": "center",
  "spans": []
}
```

### 3. `PAGE_BREAK`
Manually forces all subsequent blocks to render on a new A4 page container. Requires no other properties.
```json
{
  "id": "blk_page_break_1",
  "type": "PAGE_BREAK"
}
```

### 4. `LIST`
Supports ordered or bulleted lists with deep nesting capabilities.
```json
{
  "id": "blk_list",
  "type": "LIST",
  "list_type": "bullet", // "bullet" or "ordered"
  "items": [
    {
      "level": 0, // Nesting level (0 = root, 1 = indented once, etc.)
      "refs": [],
      "spans": [{ "text": "Bullet point 1" }]
    },
    {
      "level": 1,
      "spans": [{ "text": "Nested bullet point A" }]
    }
  ]
}
```

### 5. `TABLE`
Grid data structure.
```json
{
  "id": "blk_table",
  "type": "TABLE",
  "rows": [
    {
      "cells": [
        {
          "isHeader": true, // Renders as <th> if true, <td> if false
          "colspan": 1,
          "rowspan": 1,
          "colwidth": 150, // Optional exact pixel width
          "spans": [{ "text": "Header Cell" }]
        }
      ]
    }
  ]
}
```

### 6. `TOC` (Table of Contents)
Generates the specific dot-leader indexed format.
```json
{
  "id": "blk_toc",
  "type": "TOC",
  "entries": [
    {
      "id": "toc_1",
      "level": 0, // 0 = bold top-level, 1+ = indented sub-level
      "text": "PART I - LONGITUDINAL PROGRESSION TIMELINE",
      "page": "6" // The target page number shown on the right
    }
  ]
}
```

### 7. `DIVIDER`
Horizontal line `<hr>`.
```json
{
  "id": "blk_hr",
  "type": "DIVIDER",
  "thickness": "1px",
  "color": "#000000"
}
```

---

## Span Objects (Inline Styling)

For blocks containing text (`HEADING`, `PARAGRAPH`, `LIST`, `TABLE`), the actual text content is broken down into an array of `spans`. Each span can carry its own inline styling and citations.

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `string` | The actual text to display. |
| `bold` | `boolean` | Bold styling. |
| `italic` | `boolean` | Italic styling. |
| `underline` | `boolean` | Underline styling. |
| `fontSize` | `string` | CSS font size (e.g., `"14pt"`, `"24px"`). |
| `refs` | `array[string]` | Generates a clickable inline citation (e.g. `[1]`) immediately after this span of text. Maps to the `references` object at the root. |

**Example of mixed spans:**
```json
"spans": [
  { "text": "David W. Burns", "bold": true, "fontSize": "14pt" },
  { "text": " (Evaluator)" },
  { "text": "[1]", "refs": ["ref_1"] }
]
```
