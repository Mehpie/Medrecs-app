import React from 'react';
import SplitPane from './components/Layout/SplitPane';
import TipTapEditor from './components/Editor/TipTapEditor';
import PDFViewer from './components/PDFViewer/PDFViewer';
import { godPayload } from './utils/mockData';

function App() {
  return (
    <div className="min-h-screen font-sans">
      <SplitPane 
        leftPane={
          <TipTapEditor initialBackendData={godPayload} />
        }
        rightPane={
          <PDFViewer 
            pdfUrl="/mock.pdf" 
            referencesData={godPayload.references} 
          />
        }
      />
    </div>
  );
}

export default App;
