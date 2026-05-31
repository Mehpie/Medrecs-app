import React from 'react';

const HighlightBox = ({ boundingBox }) => {
  if (!boundingBox || boundingBox.length !== 4) return null;

  const [xMin, yMin, xMax, yMax] = boundingBox;

  // React-pdf renders the page at a specific scale.
  // The bounding boxes from the backend are often relative (0 to 1).
  // Assuming they are relative to page width and height:
  const left = `${xMin * 100}%`;
  const top = `${yMin * 100}%`;
  const width = `${(xMax - xMin) * 100}%`;
  const height = `${(yMax - yMin) * 100}%`;

  return (
    <div
      className="absolute bg-yellow-300 mix-blend-multiply opacity-50 pointer-events-none z-10"
      style={{
        left,
        top,
        width,
        height,
      }}
    />
  );
};

export default HighlightBox;
