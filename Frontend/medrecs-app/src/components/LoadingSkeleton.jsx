import React from 'react';

export default function LoadingSkeleton() {
  return (
    <div className="flex flex-col w-full mt-8">
      <div className="hidden sm:grid grid-cols-12 gap-4 px-6 py-4 border-b border-content sticky top-0 bg-background z-10 opacity-50 shadow-none">
        <div className="col-span-3 border-r border-content/20 pr-4 h-4 bg-content/30 animate-pulse"></div>
        <div className="col-span-4 border-r border-content/20 px-4 h-4 bg-content/30 animate-pulse"></div>
        <div className="col-span-1 border-r border-content/20 px-4 h-4 bg-content/30 animate-pulse"></div>
        <div className="col-span-2 border-r border-content/20 px-4 pl-8 h-4 bg-content/30 animate-pulse"></div>
        <div className="col-span-2 pl-4 h-4 bg-content/30 animate-pulse"></div>
      </div>
      <div className="flex flex-col gap-3 py-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="grid grid-cols-12 gap-4 px-6 py-5 bg-background border border-content rounded-none shadow-none items-center relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-content opacity-20"></div>
            <div className="col-span-12 sm:col-span-3 flex flex-col gap-2">
              <div className="h-6 w-24 bg-content/30 animate-pulse"></div>
              <div className="h-4 w-16 bg-content/30 animate-pulse"></div>
            </div>
            <div className="col-span-12 sm:col-span-4 flex flex-col gap-2">
              <div className="h-5 w-48 bg-content/30 animate-pulse"></div>
              <div className="h-4 w-32 bg-content/30 animate-pulse"></div>
            </div>
            <div className="col-span-6 sm:col-span-1 flex sm:justify-end">
              <div className="h-5 w-12 bg-content/30 animate-pulse"></div>
            </div>
            <div className="col-span-6 sm:col-span-2 sm:pl-8 flex items-center gap-2">
              <div className="w-2 h-2 rounded-none bg-content/30 animate-pulse shrink-0 border border-content/30"></div>
              <div className="h-4 w-20 bg-content/30 animate-pulse"></div>
            </div>
            <div className="col-span-12 sm:col-span-2 flex sm:justify-end">
              <div className="h-4 w-32 bg-content/30 animate-pulse"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
