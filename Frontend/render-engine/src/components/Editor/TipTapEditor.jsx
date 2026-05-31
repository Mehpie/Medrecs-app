import React, { useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TextAlign from '@tiptap/extension-text-align';
import ListItem from '@tiptap/extension-list-item';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import debounce from 'lodash.debounce';

import { CitationNode } from './extensions/CitationNode';
import { BlockReference } from './extensions/BlockReference';
import { TocNode } from './extensions/TocNode';
import { PageExtension } from './extensions/PageExtension';
import { FontSize } from './extensions/FontSize';
import Document from '@tiptap/extension-document';
import { convertBackendToTipTap, convertTipTapToBackend } from '../../utils/adapter';

// Custom Document that requires at least one Page node, which contains the actual blocks
const CustomDocument = Document.extend({
  content: 'page+',
});

export const EditableContext = React.createContext(false);

const TipTapEditor = ({ initialBackendData }) => {
  const [isEditable, setIsEditable] = useState(false);

  // 1. Adapter: Convert Backend JSON to TipTap JSON on load
  const initialContent = convertBackendToTipTap(initialBackendData);

  // 2. The Auto-Save Function
  const saveToBackend = useCallback(
    debounce(async (tiptapJson, forceLog = false) => {
      // Adapter: Convert TipTap JSON back to Backend format
      const backendPayload = convertTipTapToBackend(tiptapJson, initialBackendData);
      
      // Mock API call
      if (forceLog) {
        console.log('Saved to backend payload:', backendPayload);
      }
      
    }, 1500),
    [initialBackendData]
  );

  const editor = useEditor({
    editable: isEditable,
    extensions: [
      StarterKit.configure({
        document: false, // We provide our own CustomDocument
        heading: {
          levels: [1, 2, 3, 4, 5, 6],
        },
      }),
      CustomDocument,
      PageExtension,
      FontSize,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      ListItem,
      CitationNode,
      BlockReference,
      TocNode,
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: initialContent,
    onUpdate: ({ editor }) => {
      // Trigger debounced save on every edit
      saveToBackend(editor.getJSON(), false);
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm sm:prose-base focus:outline-none max-w-none',
      },
    },
  });

  // Update editor editable state when isEditable changes
  React.useEffect(() => {
    if (editor) {
      editor.setEditable(isEditable);
    }
  }, [isEditable, editor]);

  const handleEditSaveToggle = () => {
    if (isEditable) {
      // Transitioning from Edit -> Save
      if (editor) {
        // Cancel any pending debounced saves and save immediately
        saveToBackend.cancel();
        
        const tiptapJson = editor.getJSON();
        const backendPayload = convertTipTapToBackend(tiptapJson, initialBackendData);
        console.log('Saved to backend payload:', backendPayload);
        
        // Forcefully clear focus and any active node selection "blue boxes"
        editor.commands.blur();
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
        // Hack to remove ProseMirror's sticky selected node class
        window.getSelection()?.removeAllRanges();
      }
    }
    setIsEditable(!isEditable);
  };

  return (
    <EditableContext.Provider value={isEditable}>
      <div className="bg-transparent w-full h-full pb-16 relative">
        <div className="sticky top-4 z-50 flex justify-end pr-8 print:hidden gap-2">
          <button 
            onClick={handleEditSaveToggle}
            className={`${isEditable ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-700 hover:bg-gray-800'} text-white font-bold py-2 px-4 rounded shadow-lg transition-colors flex items-center gap-2`}
          >
            {isEditable ? (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                Save
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                </svg>
                Edit
              </>
            )}
          </button>
          <button 
            onClick={() => window.print()}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded shadow-lg transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
            </svg>
            Print to PDF
          </button>
        </div>
        <EditorContent editor={editor} />
      </div>
    </EditableContext.Provider>
  );
};

export default TipTapEditor;
