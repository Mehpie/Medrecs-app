import React from 'react';
import CaseRow from './CaseRow';

export default function CaseList({ cases }) {
  return (
    <div className="flex flex-col w-full mt-8 overflow-y-auto max-h-[60vh] custom-scrollbar border-b border-content/15 overscroll-contain backdrop-blur-sm">
      {/* Table Header */}
      <div className="hidden sm:grid grid-cols-12 gap-4 px-6 py-4 border-b border-content/15 font-label-caps font-bold text-label-caps text-content uppercase tracking-widest sticky top-0 bg-[#E8E7E2] dark:bg-[#15171A] z-20 shadow-none">
        <div className="col-span-3 border-r border-content/20 pr-4">CASE ID / REF</div>
        <div className="col-span-4 border-r border-content/20 px-4">SUBJECT / CLIENT</div>
        <div className="col-span-1 border-r border-content/20 px-4 text-right">DOCS</div>
        <div className="col-span-2 border-r border-content/20 px-4 pl-8">STATUS</div>
        <div className="col-span-2 pl-4 text-right">LAST TELEMETRY</div>
      </div>
      
      {/* Ledger Cards */}
      <div className="flex flex-col gap-3 py-4">
        {cases.map((c) => (
          <CaseRow key={c.id} data={c} />
        ))}
        
        {/* End Placeholder Card */}
        <div className="grid grid-cols-12 gap-4 px-6 py-8 bg-background border border-content/20 border-dashed rounded-none opacity-50 mt-4 shadow-none">
          <div className="col-span-12 flex justify-center items-center">
            <span className="font-data-sm text-data-sm text-content">// END OF RECORD</span>
          </div>
        </div>
      </div>
    </div>
  );
}
