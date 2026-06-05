import React from 'react';
import { Loader2 } from 'lucide-react';

export default function StatusBadge({ status, eta }) {
  const isProcessing = status === 'PROCESSING';
  const label = isProcessing && eta ? `ETA ${eta}` : status;

  const isNeutral = ['DRAFT', 'CLOSED', 'ARCHIVED'].includes(status);
  const isPending = ['PROCESSING', 'ETA'].includes(status) || isProcessing;
  const isSuccess = ['REVIEW', 'APPROVED'].includes(status);

  let textColor = 'text-content';
  let borderColor = 'border-content/20';

  if (isNeutral) {
    textColor = 'text-content/70';
    borderColor = 'border-content/20';
  } else if (isPending) {
    textColor = 'text-pending';
    borderColor = 'border-pending/40';
  } else if (isSuccess) {
    textColor = 'text-success';
    borderColor = 'border-success/40';
  }

  return (
    <div className={`flex items-center gap-2 ${textColor}`}>
      {isProcessing ? (
        <Loader2 className="w-3 h-3 animate-spin shrink-0" />
      ) : (
        <div className="w-2 h-2 rounded-none shrink-0 border border-current bg-transparent"></div>
      )}
      <span className={`font-mono uppercase tracking-wide border-b ${borderColor} pb-0.5 whitespace-nowrap text-[11px] font-bold`}>
        {label}
      </span>
    </div>
  );
}
