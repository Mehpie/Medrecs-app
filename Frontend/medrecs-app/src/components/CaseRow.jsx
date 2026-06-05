import React from 'react';
import StatusBadge from './StatusBadge';

const CaseRow = React.memo(function CaseRow({ data }) {
  const renderData = (val, isNumber = false) => {
    if (val === null || val === undefined || val === '') {
      return <span className="opacity-40">// NULL</span>;
    }
    return isNumber ? val.toLocaleString() : val;
  };

  return (
    <div className="grid grid-cols-12 gap-4 px-6 py-5 bg-white/20 dark:bg-surface/30 border-b border-content/10 border-t-0 border-r-0 border-l-4 border-l-transparent hover:border-l-content hover:bg-white/40 dark:hover:bg-surface/50 transition-all duration-150 group items-center relative overflow-hidden">
      
      {/* Unread Badge */}
      {data.unread && (
        <div className="absolute right-0 top-0 w-0 h-0 border-t-[16px] border-r-[16px] border-t-interactive border-r-transparent transition-colors"></div>
      )}

      <div className="col-span-12 sm:col-span-3 flex flex-col">
        <span className="font-data-lg tabular-nums font-bold text-[18px] text-content">{renderData(data.id)}</span>
        <span className="font-data-sm tabular-nums text-content opacity-70">{renderData(data.reference)}</span>
      </div>
      <div className="col-span-12 sm:col-span-4 flex flex-col mt-2 sm:mt-0">
        <span className="font-body-main font-bold uppercase truncate pr-4 text-content">{renderData(data.name)}</span>
        <span className="font-body-main opacity-70 truncate pr-4 text-content">{renderData(data.clientName)}</span>
      </div>
      <div className="col-span-6 sm:col-span-1 font-data-sm tabular-nums text-left sm:text-right mt-2 sm:mt-0 text-content">
        {renderData(data.docsCount, true)}
      </div>
      <div className="col-span-6 sm:col-span-2 sm:pl-8 flex items-center mt-2 sm:mt-0">
        <StatusBadge status={data.status} eta={data.eta} />
      </div>
      <div className="col-span-12 sm:col-span-2 font-data-sm tabular-nums text-left sm:text-right mt-2 sm:mt-0 text-content opacity-70">
        {renderData(data.lastTelemetry)}
      </div>
    </div>
  );
});

export default CaseRow;
