import { Extension } from '@tiptap/core';

export const BlockReference = Extension.create({
  name: 'blockReference',

  addGlobalAttributes() {
    return [
      {
        types: ['heading', 'paragraph', 'listItem', 'toc', 'horizontalRule'],
        attributes: {
          blockRefs: {
            default: [],
            parseHTML: element => {
              const refs = element.getAttribute('data-block-refs');
              return refs ? JSON.parse(refs) : [];
            },
            renderHTML: attributes => {
              if (!attributes.blockRefs || attributes.blockRefs.length === 0) {
                return {};
              }
              return {
                'data-block-refs': JSON.stringify(attributes.blockRefs),
              };
            },
          },
          marginBottom: {
            default: null, // Don't default to 16px to avoid spacing out list items
            parseHTML: element => element.style.marginBottom || null,
            renderHTML: attributes => {
              if (!attributes.marginBottom) return {};
              return {
                style: `margin-bottom: ${attributes.marginBottom}`,
              };
            },
          },
          lineNumber: {
            default: null,
            parseHTML: element => element.getAttribute('data-line-number'),
            renderHTML: attributes => {
              if (!attributes.lineNumber) return {};
              return { 'data-line-number': attributes.lineNumber };
            }
          },
          id: {
            default: null,
            parseHTML: element => element.getAttribute('id'),
            renderHTML: attributes => {
              if (!attributes.id) return {};
              return { id: attributes.id };
            }
          }
        },
      },
    ];
  },
});
