import React from 'react';

export default function DashboardSkeleton() {
  const ghostRows = Array.from({ length: 6 });
  
  return (
    <div className="flex flex-col w-full mt-8 overflow-y-auto max-h-[60vh] custom-scrollbar border-b border-content/15">
      {/* Table Header Skeleton */}
      <div className="hidden sm:grid grid-cols-12 gap-4 px-6 py-4 border-b border-content/15 sticky top-0 bg-[#E8E7E2] dark:bg-[#15171A] z-20 shadow-none">
        <div className="col-span-3 border-r border-content/20 pr-4">
          <div className="h-4 w-24 bg-content/10 rounded-none animate-pulse"></div>
        </div>
        <div className="col-span-4 border-r border-content/20 px-4">
          <div className="h-4 w-32 bg-content/10 rounded-none animate-pulse"></div>
        </div>
        <div className="col-span-1 border-r border-content/20 px-4 flex justify-end">
          <div className="h-4 w-12 bg-content/10 rounded-none animate-pulse"></div>
        </div>
        <div className="col-span-2 border-r border-content/20 px-4 pl-8">
          <div className="h-4 w-16 bg-content/10 rounded-none animate-pulse"></div>
        </div>
        <div className="col-span-2 pl-4 flex justify-end">
          <div className="h-4 w-24 bg-content/10 rounded-none animate-pulse"></div>
        </div>
      </div>
      
      {/* Ghost Rows */}
      <div className="flex flex-col gap-3 py-4">
        {ghostRows.map((_, i) => {
          // Provide randomized widths to mimic real text length
          const idWidth = ['w-24', 'w-20', 'w-28'][i % 3];
          const refWidth = ['w-16', 'w-20', 'w-12'][i % 3];
          const subjectWidth = ['w-48', 'w-32', 'w-56', 'w-full max-w-[120px]'][i % 4];
          const clientWidth = ['w-32', 'w-40', 'w-24', 'w-36'][i % 4];
          const docsWidth = ['w-8', 'w-12', 'w-16'][i % 3];
          const statusWidth = ['w-16', 'w-20', 'w-24'][i % 3];
          const telemetryWidth = ['w-32', 'w-40', 'w-36'][i % 3];

          return (
            <div key={i} className="grid grid-cols-12 gap-4 px-6 py-5 bg-white/20 dark:bg-surface/30 backdrop-blur-sm border-b border-content/10 border-t-0 border-r-0 border-l-4 border-l-transparent items-center relative overflow-hidden">
              <div className="col-span-12 sm:col-span-3 flex flex-col gap-2">
                <div className={`h-5 ${idWidth} bg-content/10 rounded-none animate-pulse`}></div>
                <div className={`h-4 ${refWidth} bg-content/10 rounded-none animate-pulse`}></div>
              </div>
              <div className="col-span-12 sm:col-span-4 flex flex-col gap-2 mt-2 sm:mt-0">
                <div className={`h-5 ${subjectWidth} bg-content/10 rounded-none animate-pulse`}></div>
                <div className={`h-4 ${clientWidth} bg-content/10 rounded-none animate-pulse`}></div>
              </div>
              <div className="col-span-6 sm:col-span-1 flex sm:justify-end mt-2 sm:mt-0">
                <div className={`h-4 ${docsWidth} bg-content/10 rounded-none animate-pulse`}></div>
              </div>
              <div className="col-span-6 sm:col-span-2 sm:pl-8 flex items-center gap-2 mt-2 sm:mt-0">
                <div className={`h-4 ${statusWidth} bg-content/10 rounded-none animate-pulse`}></div>
              </div>
              <div className="col-span-12 sm:col-span-2 flex sm:justify-end mt-2 sm:mt-0">
                <div className={`h-4 ${telemetryWidth} bg-content/10 rounded-none animate-pulse`}></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
