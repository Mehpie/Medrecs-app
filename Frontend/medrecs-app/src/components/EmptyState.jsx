import React from 'react';
import { FolderPlus } from 'lucide-react';

export default function EmptyState({ onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 bg-background border border-content border-dashed rounded-none text-center shadow-none mt-8">
      <div className="w-16 h-16 mb-4 flex items-center justify-center bg-transparent border border-content text-content rounded-none">
        <FolderPlus className="w-8 h-8" />
      </div>
      <h3 className="font-headline-md font-bold text-[24px] text-content mb-2">NO CASES FOUND</h3>
      <p className="font-body-main text-content opacity-70 mb-6 max-w-md">
        There are currently no cases matching your criteria. Create your first case to get started with DART analysis.
      </p>
      <button 
        onClick={onAction}
        className="flex items-center justify-center gap-2 bg-content text-background px-6 py-2 font-label-caps font-bold uppercase tracking-widest hover:bg-interactive transition-colors rounded-none border border-content shadow-none"
      >
        <FolderPlus className="w-4 h-4" />
        CREATE YOUR FIRST CASE
      </button>
    </div>
  );
}
