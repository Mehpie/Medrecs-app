import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import PageNodeView from './PageNodeView';

// A4 height in CSS: 297mm = 1123px at 96 DPI
// We use this as the maximum page height before triggering overflow redistribution.
const A4_HEIGHT_PX = 297 * (96 / 25.4); // ≈ 1123px

export const PageExtension = Node.create({
  name: 'page',
  group: 'pageGroup',
  content: 'block+',

  addAttributes() {
    return {
      pageNumber: { default: 1 },
      totalPages: { default: 1 },
      startLineNumber: { default: 1 },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="page"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-type': 'page' }), 0];
  },

  addNodeView() {
    return ReactNodeViewRenderer(PageNodeView);
  },

  addProseMirrorPlugins() {
    let timer = null;
    let isProcessing = false;

    return [
      new Plugin({
        key: new PluginKey('pageOverflow'),
        view: () => ({
          update: (view, prevState) => {
            // Skip if we're already processing or doc hasn't changed
            if (isProcessing) return;

            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
              isProcessing = true;
              try {
                handlePageOverflow(view);
              } finally {
                // Small delay before allowing next check to let React re-render
                setTimeout(() => { isProcessing = false; }, 150);
              }
            }, 250);
          },
        }),
      }),
    ];
  },
});

/**
 * Check all pages for overflow. If any page's rendered height exceeds A4,
 * move the last block to the next page (creating one if needed).
 * 
 * We move ONE block per invocation and let the plugin re-trigger for
 * cascading overflows. This is simple, correct, and avoids complex
 * position arithmetic.
 */
function handlePageOverflow(view) {
  const { state } = view;
  const doc = state.doc;
  const pageType = state.schema.nodes.page;

  // Collect page info
  const pages = [];
  doc.forEach((node, offset) => {
    if (node.type.name === 'page') {
      pages.push({ node, offset });
    }
  });

  if (pages.length === 0) return;

  // Find the first page that overflows
  let overflowIdx = -1;
  for (let i = 0; i < pages.length; i++) {
    const { offset } = pages[i];
    const pageDOM = view.nodeDOM(offset);
    if (!pageDOM) continue;

    // The page uses min-h-[297mm], so if content overflows it grows taller.
    // Compare actual rendered height to A4 height.
    const actualHeight = pageDOM.offsetHeight;
    if (actualHeight > A4_HEIGHT_PX + 10) {
      overflowIdx = i;
      break;
    }
  }

  if (overflowIdx === -1) return; // No overflow detected

  const { node: pageNode, offset: pageOffset } = pages[overflowIdx];

  // Can't move if the page has only one block
  if (pageNode.childCount <= 1) return;

  // Get the last child of the overflowing page
  const lastChild = pageNode.child(pageNode.childCount - 1);

  // Position arithmetic:
  // Page node spans [pageOffset, pageOffset + pageNode.nodeSize)
  // Opening tag: pageOffset
  // Content: [pageOffset + 1, pageOffset + pageNode.nodeSize - 1)
  // Last child: [pageOffset + pageNode.nodeSize - 1 - lastChild.nodeSize, pageOffset + pageNode.nodeSize - 1)
  const lastChildStart = pageOffset + pageNode.nodeSize - 1 - lastChild.nodeSize;
  const lastChildEnd = pageOffset + pageNode.nodeSize - 1;

  const tr = state.tr;

  // Step 1: Delete the last child from the overflowing page
  tr.delete(lastChildStart, lastChildEnd);

  // Step 2: Insert into the next page or create a new one
  if (overflowIdx + 1 < pages.length) {
    // Next page exists — insert at its beginning
    const nextPageOffset = pages[overflowIdx + 1].offset;
    const mappedInsertPos = tr.mapping.map(nextPageOffset + 1);
    tr.insert(mappedInsertPos, lastChild);
  } else {
    // No next page — create a new page with this block
    const newPageNode = pageType.create(
      {
        pageNumber: pageNode.attrs.pageNumber + 1,
        totalPages: pageNode.attrs.totalPages,
        startLineNumber: 1,
      },
      [lastChild]
    );
    // Insert after the current page
    const insertAfter = tr.mapping.map(pageOffset + pageNode.nodeSize);
    tr.insert(insertAfter, newPageNode);
  }

  // Step 3: Update page numbers and total pages across all pages
  // Count pages first
  let total = 0;
  tr.doc.forEach((node) => {
    if (node.type.name === 'page') total++;
  });

  // Now update attrs — offsets from tr.doc are already in transformed position space
  let pageNum = 1;
  tr.doc.forEach((node, offset) => {
    if (node.type.name === 'page') {
      if (node.attrs.pageNumber !== pageNum || node.attrs.totalPages !== total) {
        tr.setNodeMarkup(offset, undefined, {
          ...node.attrs,
          pageNumber: pageNum,
          totalPages: total,
        });
      }
      pageNum++;
    }
  });

  view.dispatch(tr);
}
