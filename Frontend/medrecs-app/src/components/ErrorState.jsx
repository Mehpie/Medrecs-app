import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function ErrorState({ onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 bg-background border border-pending border-dashed rounded-none text-center shadow-none mt-8">
      <AlertTriangle className="w-12 h-12 text-pending mb-4" />
      <h3 className="font-headline-md font-bold text-[24px] text-pending mb-2">TELEMETRY FAILURE</h3>
      <p className="font-body-main text-content opacity-70 mb-6">
        Unable to sync ledger data from the secure network.
      </p>
      <button 
        onClick={onRetry}
        className="flex items-center justify-center gap-2 bg-transparent text-pending px-6 py-2 font-label-caps font-bold uppercase tracking-widest hover:bg-pending hover:text-background transition-colors rounded-none border border-pending shadow-none"
      >
        <RefreshCw className="w-4 h-4" />
        RETRY CONNECTION
      </button>
    </div>
  );
}
