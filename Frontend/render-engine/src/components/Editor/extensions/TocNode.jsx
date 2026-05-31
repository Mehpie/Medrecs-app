import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react';
import React, { useContext } from 'react';
import { EditableContext } from '../TipTapEditor';

const TocComponent = ({ node, updateAttributes }) => {
  const entries = node.attrs.entries || [];
  const isEditable = useContext(EditableContext);

  const handleUpdateEntry = (idx, field, value) => {
    const newEntries = [...entries];
    newEntries[idx] = { ...newEntries[idx], [field]: value };
    updateAttributes({ entries: newEntries });
  };

  return (
    <NodeViewWrapper className="toc-container mb-8">
      <h2 className="text-[14pt] font-bold m-0 leading-[22px] text-center" style={{ fontFamily: '"Times New Roman", Times, serif' }}>INDEX</h2>
      <div className="h-[22px]"></div>
      <div className="flex flex-col gap-0">
        {entries.map((entry, idx) => (
          <div
            key={entry.id || idx}
            className="flex items-end m-0 leading-[22px] h-[22px]"
            style={{ paddingLeft: `${(entry.level || 0) * 1.5}rem` }}
          >
            {isEditable ? (
              <div className="relative inline-grid items-end" style={{ flexShrink: 0, maxWidth: '80%' }}>
                <span className={`invisible whitespace-pre col-start-1 row-start-1 pr-2 ${entry.level === 0 ? 'font-bold' : ''}`}>
                  {entry.title || 'Title'}
                </span>
                <input
                  type="text"
                  value={entry.title || ''}
                  onChange={(e) => handleUpdateEntry(idx, 'title', e.target.value)}
                  className={`col-start-1 row-start-1 w-full bg-transparent outline-none border-b border-dashed border-gray-300 focus:border-blue-500 hover:bg-gray-50 pr-2 transition-colors ${entry.level === 0 ? 'font-bold' : ''}`}
                  placeholder="Title"
                />
              </div>
            ) : (
              <span className={`pr-2 ${entry.level === 0 ? 'font-bold' : ''}`}>
                {entry.title}
              </span>
            )}
            
            <div className="flex-1 border-b border-dotted border-black mb-[6px] mx-2"></div>
            
            {isEditable ? (
              <input
                type="text"
                value={entry.page_number || ''}
                onChange={(e) => handleUpdateEntry(idx, 'page_number', e.target.value)}
                className="pl-2 bg-transparent hover:bg-gray-50 outline-none border-b border-dashed border-gray-300 focus:border-blue-500 w-12 text-right transition-colors"
                placeholder="Pg"
              />
            ) : (
              <span className="pl-2">{entry.page_number}</span>
            )}
          </div>
        ))}
      </div>
    </NodeViewWrapper>
  );
};

export const TocNode = Node.create({
  name: 'toc',
  group: 'block',
  atom: true,

  addAttributes() {
    return {
      entries: { default: [] },
      id: { default: null },
      marginBottom: { default: '32px' }
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="toc"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-type': 'toc' })];
  },

  addNodeView() {
    return ReactNodeViewRenderer(TocComponent);
  },
});
