import React from 'react';

const SplitPane = ({ leftPane, rightPane }) => {
  return (
    <div className="flex h-screen w-full bg-gray-100 overflow-hidden print:h-auto print:block print:overflow-visible print:bg-white">
      {/* Left Pane: Editor */}
      <div className="w-1/2 h-full overflow-y-auto border-r border-gray-300 bg-gray-50 flex justify-center print:w-full print:h-auto print:overflow-visible print:border-none print:bg-white print:block">
        {leftPane}
      </div>

      {/* Right Pane: PDF Viewer */}
      <div className="w-1/2 h-full overflow-y-auto bg-gray-200 flex justify-center items-center print:hidden">
        {rightPane}
      </div>
    </div>
  );
};

export default SplitPane;
