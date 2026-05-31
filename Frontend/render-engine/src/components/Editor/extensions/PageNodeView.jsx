import React from 'react';
import { NodeViewWrapper, NodeViewContent } from '@tiptap/react';
import LineNumbersGutter from '../LineNumbersGutter';

const PageNodeView = (props) => {
  const { node, editor } = props;
  const pageNum = node.attrs.pageNumber || 1;
  const totalPages = node.attrs.totalPages || 1;
  const startLine = node.attrs.startLineNumber || 1;

  return (
    <NodeViewWrapper data-type="page" className="w-[210mm] min-h-[297mm] my-8 mx-auto bg-white shadow-lg relative print:m-0 print:shadow-none flex flex-col font-serif text-[11pt] leading-[1.5]">
      {/* Top Header */}
      <div className="text-center pt-8 text-[10pt] text-gray-700">
        Examinee: Atarah Phillips | DOL: 4/13/2023 | Evaluator: David Burns, ND, FACFN, FABBIR
      </div>

      {/* Main Content Area with Border */}
      <div className="flex flex-1 mt-6 mx-12 relative">
        <LineNumbersGutter editor={editor} startNumber={startLine} scopedNodeId={node.attrs.id || `page-${pageNum}`} />
        
        {/* The Bordered Box containing the page's blocks */}
        <div className="flex-1 border border-black relative z-10 outline-none pb-4 ml-12">
          {/* NodeViewContent acts as the container for this node's children */}
          <NodeViewContent className="p-4 pr-4 relative z-10 outline-none min-h-full" />
        </div>
      </div>

      {/* Bottom Footer */}
      <div className="text-right pb-8 pr-12 pt-2 text-[10pt] font-bold">
        Page {pageNum} of {totalPages}
      </div>
    </NodeViewWrapper>
  );
};

export default PageNodeView;
