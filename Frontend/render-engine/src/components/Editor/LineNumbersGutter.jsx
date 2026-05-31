import React, { useEffect, useState, useRef } from 'react';

const LineNumbersGutter = ({ editor, startNumber = 1, scopedNodeId }) => {
  const [lineData, setLineData] = useState([]);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!editor || !editor.view || !editor.view.dom) return;

    const editorDom = editor.view.dom;

    const updateLineNumbers = () => {
      const newLines = [];
      let currentNumber = startNumber;
      
      if (!containerRef.current) return;
      
      // If we have a scoped DOM node (the page), only query inside it
      // The parent of the containerRef is the flex container, its parent is the NodeViewWrapper.
      const pageNode = containerRef.current.closest('[data-type="page"]') || editorDom;
      // Get ALL text-containing block elements in the entire document
      const allBlocks = editorDom.querySelectorAll('p, h1, h2, h3, h4, h5, h6, .toc-container');
      const containerRect = containerRef.current.getBoundingClientRect();

      allBlocks.forEach(block => {
        // Skip blocks inside tables as per PDF behavior
        if (block.closest('table')) return;
        // Number the toc-container as a single block based on height, skip its children
        if (block.closest('.toc-container') && block !== block.closest('.toc-container')) return;

        const blockRect = block.getBoundingClientRect();
        if (blockRect.height === 0 || block.innerText.trim() === '') return;

        const computedStyle = window.getComputedStyle(block);
        const lineHeightStr = computedStyle.lineHeight;
        
        let lineHeight = 22; 
        if (lineHeightStr !== 'normal') {
          lineHeight = parseFloat(lineHeightStr);
        }

        const numLines = Math.max(1, Math.round(blockRect.height / lineHeight));

        // Check if this block belongs to the CURRENT page
        const isCurrentPage = block.closest('[data-type="page"]') === pageNode;

        if (isCurrentPage) {
          const topRelativeToContainer = blockRect.top - containerRect.top;
          
          for (let i = 0; i < numLines; i++) {
            newLines.push({
              number: currentNumber++,
              top: topRelativeToContainer + (i * lineHeight),
              height: lineHeight
            });
          }
        } else {
          // Block is on a different page, just increment the global counter
          currentNumber += numLines;
        }
      });

      setLineData(newLines);
    };

    // Initial update
    updateLineNumbers();

    // Listen to editor changes
    editor.on('transaction', updateLineNumbers);

    // Listen to window resizes (which changes text wrapping)
    window.addEventListener('resize', updateLineNumbers);

    // Setup a ResizeObserver on the editor DOM just in case fonts load or layout shifts
    const resizeObserver = new ResizeObserver(() => {
      updateLineNumbers();
    });
    resizeObserver.observe(editorDom);

    return () => {
      editor.off('transaction', updateLineNumbers);
      window.removeEventListener('resize', updateLineNumbers);
      resizeObserver.disconnect();
    };
  }, [editor, startNumber]);

  return (
    <div 
      ref={containerRef}
      className="absolute left-0 top-0 bottom-0 w-12 border-r border-transparent pointer-events-none z-0"
    >
      <div className="relative w-full h-full text-[11pt] font-serif text-gray-700 text-right pr-2">
        {lineData.map((line, idx) => (
          <div 
            key={idx} 
            className="absolute right-4 w-full flex items-center justify-end"
            style={{ 
              top: `${line.top}px`, 
              height: `${line.height}px`,
              lineHeight: `${line.height}px` 
            }}
          >
            {line.number}
          </div>
        ))}
      </div>
    </div>
  );
};

export default LineNumbersGutter;
