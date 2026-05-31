# Step 1: Initial Frontend Architecture & Rendering Engine

This document outlines the first phase of development for the MedRecs Lawyer Preparation Report editor.

## Objectives Accomplished

1. **Project Initialization**
   - Initialized a React + Vite project.
   - Configured Tailwind CSS for styling.

2. **Core Layout**
   - Created a split-pane layout using CSS Grid (`src/components/Layout/SplitPane.jsx`).
   - Left side: A continuous A4-styled document editor.
   - Right side: A PDF viewer for document references.

3. **State Management (Zustand)**
   - Created a simple global state store (`src/store/useReferenceStore.js`).
   - Manages the `activeReference` ID, allowing independent components (TipTap editor and react-pdf) to react to user interactions without prop drilling.

4. **Rich Text Editor (TipTap)**
   - Integrated TipTap as the headless rich-text editor engine to manage the complex, highly structured document state.
   - Built custom TipTap extensions:
     - `CitationNode`: An inline React Node View rendering clickable superscripts `[1]`. Updates the Zustand store upon click.
     - `BlockReference`: Adds custom attributes (`blockRefs`, `marginBottom`) to core block nodes. Used for rendering right-hand gutter citations.
     - `TocNode`: A specialized node to render the Table of Contents dynamically.
   - Wrapped the editor in an A4 container to replicate the print-ready visual style (`EditorA4Container.jsx`).
   - Added a debounced auto-save mechanism that serializes the editor's internal JSON and maps it back to the backend schema.

5. **JSON Data Mapping Pipeline**
   - Created data adapters (`src/utils/adapter.js`) to translate the required strict backend JSON structure into TipTap's native Prosemirror JSON structure, and vice versa.
   - Implemented a "God Payload" mockup (`src/utils/mockData.js`) to test the complex rendering requirements.

6. **PDF Viewer (react-pdf)**
   - Integrated `react-pdf` to display reference source documents (`src/components/PDFViewer/PDFViewer.jsx`).
   - Listens to the Zustand `activeReference` state.
   - Automatically navigates to the associated `source_page` when a reference is activated.
   - Renders a semi-transparent yellow `HighlightBox` overlay using the backend-provided `bounding_boxes` coordinates.

## Next Steps
- Implement recursive processing for infinitely nested lists in the JSON adapter.
- Connect the frontend to actual backend API endpoints.
- Enhance the UI/UX with smooth transitions and more polished loading states.
