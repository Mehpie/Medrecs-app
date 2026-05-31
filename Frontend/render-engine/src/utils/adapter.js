// Convert the custom backend JSON format to TipTap's JSON format
export function convertBackendToTipTap(backendData) {
  if (!backendData || !backendData.blocks) return { type: 'doc', content: [] };

  const pages = [];
  let currentPageBlocks = [];
  let pageNumber = 1;

  const convertBlock = (block) => {
    const attrs = {
      id: block.id,
      textAlign: block.alignment || 'left',
      blockRefs: block.refs || [],
      marginBottom: block.marginBottom || '16px',
      lineNumber: block.line_number || null,
    };

    switch (block.type) {
      case 'HEADING':
        return {
          type: 'heading',
          attrs: { ...attrs, level: parseInt(block.level) || 1 },
          content: convertSpansToTipTapNodes(block.spans),
        };

      case 'PARAGRAPH':
        return {
          type: 'paragraph',
          attrs,
          content: convertSpansToTipTapNodes(block.spans),
        };

      case 'LIST': {
        const isBullet = block.list_type === 'bullet';
        const listType = isBullet ? 'bulletList' : 'orderedList';
        
        const buildNestedList = (items, startIdx = 0, currentLevel = 0) => {
          const content = [];
          let i = startIdx;

          while (i < items.length) {
            const item = items[i];
            
            if (item.level < currentLevel) {
              break;
            } else if (item.level === currentLevel) {
              const listItem = {
                type: 'listItem',
                attrs: { blockRefs: item.refs || [] },
                content: [
                  {
                    type: 'paragraph',
                    content: convertSpansToTipTapNodes(item.spans),
                  }
                ]
              };
              
              if (i + 1 < items.length && items[i + 1].level > currentLevel) {
                const childResult = buildNestedList(items, i + 1, currentLevel + 1);
                listItem.content.push({
                  type: listType,
                  content: childResult.content
                });
                i = childResult.nextIdx;
              } else {
                i++;
              }
              content.push(listItem);
            } else {
              const childResult = buildNestedList(items, i, currentLevel + 1);
              if (content.length > 0) {
                 content[content.length - 1].content.push({
                   type: listType,
                   content: childResult.content
                 });
              } else {
                 content.push({
                   type: 'listItem',
                   content: [ { type: listType, content: childResult.content } ]
                 });
              }
              i = childResult.nextIdx;
            }
          }
          return { content, nextIdx: i };
        };

        const { content } = buildNestedList(block.items, 0, 0);

        return {
          type: listType,
          attrs,
          content
        };
      }

      case 'DIVIDER':
        return {
          type: 'horizontalRule',
          attrs: { ...attrs, thickness: block.thickness, color: block.color },
        };

      case 'TOC':
        return {
          type: 'toc',
          attrs: { ...attrs, entries: block.entries },
        };

      case 'TABLE':
        return {
          type: 'table',
          attrs,
          content: (block.rows || []).map(row => ({
            type: 'tableRow',
            content: (row.cells || []).map(cell => ({
              type: cell.isHeader ? 'tableHeader' : 'tableCell',
              attrs: {
                colspan: cell.colspan || 1,
                rowspan: cell.rowspan || 1,
                colwidth: cell.colwidth || null,
              },
              content: [
                {
                  type: 'paragraph',
                  content: convertSpansToTipTapNodes(cell.spans),
                }
              ]
            }))
          }))
        };

      default:
        return { type: 'paragraph', attrs, content: [] };
    }
  };

  backendData.blocks.forEach(block => {
    if (block.type === 'PAGE_BREAK') {
      if (currentPageBlocks.length > 0) {
        pages.push({
          type: 'page',
          attrs: { pageNumber },
          content: currentPageBlocks
        });
        pageNumber++;
        currentPageBlocks = [];
      }
    } else {
      currentPageBlocks.push(convertBlock(block));
    }
  });

  if (currentPageBlocks.length > 0) {
    pages.push({
      type: 'page',
      attrs: { pageNumber },
      content: currentPageBlocks
    });
  }

  // Update total pages for all page nodes
  pages.forEach(page => {
    page.attrs.totalPages = pages.length;
  });

  return { type: 'doc', content: pages };
}

// Convert spans (inline text with styling/refs) to TipTap text/citation nodes
function convertSpansToTipTapNodes(spans) {
  if (!spans) return [];
  
  const nodes = [];
  
  spans.forEach(span => {
    const marks = [];
    if (span.bold) marks.push({ type: 'bold' });
    if (span.italic) marks.push({ type: 'italic' });
    if (span.underline) marks.push({ type: 'underline' });
    if (span.fontSize) marks.push({ type: 'fontSize', attrs: { size: span.fontSize } });
    
    // Add the text node
    if (span.text) {
      nodes.push({
        type: 'text',
        text: span.text,
        ...(marks.length > 0 && { marks })
      });
    }

    // Add inline citation nodes after the text if refs are present
    if (span.refs && span.refs.length > 0) {
      span.refs.forEach(refId => {
        nodes.push({
          type: 'citation',
          attrs: { refId }
        });
      });
    }
  });
  
  return nodes;
}

// Convert TipTap JSON back to Backend format
export function convertTipTapToBackend(tiptapJson, originalData) {
  const blocks = [];

  const convertTipTapNodesToSpans = (nodes = []) => {
    const spans = [];
    nodes.forEach(node => {
      if (node.type === 'text') {
        const span = { text: node.text };
        if (node.marks) {
          node.marks.forEach(mark => {
            if (mark.type === 'bold') span.bold = true;
            if (mark.type === 'italic') span.italic = true;
            if (mark.type === 'underline') span.underline = true;
            if (mark.type === 'fontSize') span.fontSize = mark.attrs.size;
          });
        }
        spans.push(span);
      } else if (node.type === 'citation') {
        // Find previous span and attach ref
        if (spans.length > 0) {
          const lastSpan = spans[spans.length - 1];
          if (!lastSpan.refs) lastSpan.refs = [];
          lastSpan.refs.push(node.attrs.refId);
        }
      }
    });
    return spans;
  };

  const processBlock = (node, level = 0) => {
    const baseBlock = {
      id: node.attrs?.id || `blk_${Math.random().toString(36).substr(2, 9)}`,
      alignment: node.attrs?.textAlign || 'left',
      marginBottom: node.attrs?.marginBottom || '16px',
      refs: node.attrs?.blockRefs || [],
      line_number: node.attrs?.lineNumber || null,
    };

    if (node.type === 'heading') {
      return {
        ...baseBlock,
        type: 'HEADING',
        level: String(node.attrs.level),
        spans: convertTipTapNodesToSpans(node.content)
      };
    } else if (node.type === 'paragraph') {
      return {
        ...baseBlock,
        type: 'PARAGRAPH',
        spans: convertTipTapNodesToSpans(node.content)
      };
    } else if (node.type === 'horizontalRule') {
      return {
        ...baseBlock,
        type: 'DIVIDER',
        thickness: node.attrs?.thickness || '1px',
        color: node.attrs?.color || '#000000'
      };
    } else if (node.type === 'toc') {
      return {
        ...baseBlock,
        type: 'TOC',
        entries: node.attrs?.entries || []
      };
    } else if (node.type === 'bulletList' || node.type === 'orderedList') {
      const listBlock = {
        ...baseBlock,
        type: 'LIST',
        list_type: node.type === 'bulletList' ? 'bullet' : 'numbered',
        items: []
      };

      const flattenList = (listNode, currentLevel) => {
        const items = [];
        (listNode.content || []).forEach(listItem => {
          const item = {
            level: currentLevel,
            refs: listItem.attrs?.blockRefs || [],
            spans: []
          };
          
          (listItem.content || []).forEach(child => {
            if (child.type === 'paragraph') {
              item.spans = convertTipTapNodesToSpans(child.content);
            } else if (child.type === 'bulletList' || child.type === 'orderedList') {
              items.push(...flattenList(child, currentLevel + 1));
            }
          });
          items.push(item);
        });
        // Filter out empty items that just act as wrappers
        return items.filter(item => item.spans.length > 0 || item.refs.length > 0);
      };

      listBlock.items = flattenList(node, level);
      return listBlock;
    } else if (node.type === 'table') {
      return {
        ...baseBlock,
        type: 'TABLE',
        rows: (node.content || []).map(row => ({
          cells: (row.content || []).map(cell => ({
            isHeader: cell.type === 'tableHeader',
            colspan: cell.attrs?.colspan || 1,
            rowspan: cell.attrs?.rowspan || 1,
            colwidth: cell.attrs?.colwidth || null,
            spans: convertTipTapNodesToSpans(cell.content?.[0]?.content || [])
          }))
        }))
      };
    }

    return null;
  };

  (tiptapJson.content || []).forEach((page, pageIndex) => {
    if (page.type === 'page') {
      (page.content || []).forEach(node => {
        const block = processBlock(node);
        if (block) blocks.push(block);
      });
      
      // Add PAGE_BREAK after every page except the last one
      if (pageIndex < tiptapJson.content.length - 1) {
        blocks.push({
          id: `pb_${Math.random().toString(36).substr(2, 9)}`,
          type: 'PAGE_BREAK'
        });
      }
    }
  });

  return { ...originalData, blocks };
}
