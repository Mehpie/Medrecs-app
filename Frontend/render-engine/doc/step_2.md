# Step 2: Table Support Implementation

This document details the architecture and implementation for supporting tabular data in the MedRecs editor, matching the styling and structure of legal/medical documents.

## Proposed Changes & Implementation

### Dependencies
Installed TipTap table extensions:
- `@tiptap/extension-table`
- `@tiptap/extension-table-row`
- `@tiptap/extension-table-header`
- `@tiptap/extension-table-cell`

### Core Editor (`TipTapEditor.jsx`)
- Imported and configured the four new Table extensions.
- Added `resizable: true` to the Table extension and added them to the TipTap `useEditor` hooks.

### Data Layer (`adapter.js`)
- Added a new `case 'TABLE':` in `convertBackendToTipTap`.
- Implemented parsing logic to iterate through `rows` and map cells to either `tableHeader` or `tableCell` nodes in the TipTap JSON format.
- Mapped spans inside cells using the existing `convertSpansToTipTapNodes` function.

### Styling (`index.css`)
- Added CSS overrides to style `.ProseMirror table`.
- Ensured thick black borders, proper cell padding, and alignment.
- Set header cells (`th`) to bold.
- Replaced `table-layout: fixed` with `table-layout: auto` so columns automatically scale based on the text width inside them.

### Line Numbering (`LineNumbersGutter.jsx`)
- Added logic to exclude elements inside tables from the line number generation: `const isInsideTable = block.closest('table') !== null;`. This ensures the table body doesn't generate spurious line numbers in the left gutter, strictly mirroring the PDF aesthetic.