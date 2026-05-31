import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react';
import useReferenceStore from '../../../store/useReferenceStore';

const CitationBadgeComponent = ({ node }) => {
  const setActiveReference = useReferenceStore((state) => state.setActiveReference);
  const refId = node.attrs.refId;

  const handleRefClick = () => {
    setActiveReference(refId);
  };

  // Convert "ref_1" to "1"
  const displayRef = refId ? refId.replace('ref_', '') : '';

  return (
    <NodeViewWrapper as="span" className="inline-block">
      <sup 
        className="text-blue-600 font-bold cursor-pointer mx-1 hover:underline select-none"
        onClick={handleRefClick}
      >
        [{displayRef}]
      </sup>
    </NodeViewWrapper>
  );
};

export const CitationNode = Node.create({
  name: 'citation',
  group: 'inline',
  inline: true,
  atom: true, // User cannot edit the text inside the badge directly

  addAttributes() {
    return {
      refId: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'citation-badge' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['citation-badge', mergeAttributes(HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(CitationBadgeComponent);
  },
});
