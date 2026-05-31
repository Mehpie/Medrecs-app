import React, { useEffect, useState, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import useReferenceStore from '../../store/useReferenceStore';
import HighlightBox from './HighlightBox';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Set up the worker for react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const PDFViewer = ({ pdfUrl, referencesData }) => {
  const activeReference = useReferenceStore((state) => state.activeReference);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);

  // When activeReference changes, update the page number if valid
  useEffect(() => {
    if (activeReference && referencesData && referencesData[activeReference]) {
      const refDetails = referencesData[activeReference];
      if (refDetails.source_page) {
        setPageNumber(refDetails.source_page);
      }
    }
  }, [activeReference, referencesData]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
  };

  const activeBoundingBoxes = useMemo(() => {
    if (activeReference && referencesData && referencesData[activeReference]) {
      const refDetails = referencesData[activeReference];
      // Only show bounding boxes if they are on the current page
      if (refDetails.source_page === pageNumber && refDetails.bounding_boxes) {
        return refDetails.bounding_boxes;
      }
    }
    return [];
  }, [activeReference, referencesData, pageNumber]);

  return (
    <div className="flex flex-col items-center h-full w-full relative pt-4">
      <div className="mb-4 bg-white px-4 py-2 rounded shadow flex gap-4 items-center z-20">
        <button 
          onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
          disabled={pageNumber <= 1}
          className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
        >
          Prev
        </button>
        <span>Page {pageNumber} of {numPages || '--'}</span>
        <button 
          onClick={() => setPageNumber(Math.min(numPages || 1, pageNumber + 1))}
          disabled={pageNumber >= (numPages || 1)}
          className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>

      <div className="flex-1 overflow-auto w-full flex justify-center pb-8 shadow-inner">
        {pdfUrl ? (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            className="shadow-xl"
            loading={<div className="p-8">Loading PDF...</div>}
          >
            <div className="relative">
              <Page 
                pageNumber={pageNumber} 
                scale={scale} 
                renderTextLayer={true}
                renderAnnotationLayer={true}
              />
              {/* Render Highlight Boxes over the page */}
              {activeBoundingBoxes.map((box, idx) => (
                <HighlightBox key={idx} boundingBox={box} />
              ))}
            </div>
          </Document>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            No PDF loaded. Please provide a mock PDF file.
          </div>
        )}
      </div>
    </div>
  );
};

export default PDFViewer;
