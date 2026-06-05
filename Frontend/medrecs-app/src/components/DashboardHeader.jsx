import React, { useState, useRef, useEffect } from 'react';
import { ArrowUpDown, Plus } from 'lucide-react';

export default function DashboardHeader({ filter, setFilter, sort, setSort }) {
  const [isSortOpen, setIsSortOpen] = useState(false);
  const sortRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (sortRef.current && !sortRef.current.contains(event.target)) {
        setIsSortOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between w-full relative">
      <div className="flex flex-col gap-2 relative pl-6">
        {/* Navy Dash */}
        <div className="absolute left-0 top-[20px] w-[12px] h-[2px] bg-content"></div>
        <h1 className="font-display-lg font-bold text-[40px] md:text-display-lg text-content uppercase tracking-tight leading-none">
          DART CASE LEDGER
        </h1>
      </div>
      
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-6">
        <div className="flex overflow-x-auto items-center">
          {['All Cases', 'My Cases', 'Firm Cases', 'Archived'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest font-bold transition-all rounded-none whitespace-nowrap border-b ${
                filter === f
                  ? 'text-content border-content'
                  : 'text-content/50 border-transparent hover:text-content hover:bg-content/5'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        
        <div className="relative flex items-center" ref={sortRef}>
          <button
            onClick={() => setIsSortOpen(!isSortOpen)}
            className={`w-8 h-8 flex items-center justify-center rounded-none transition-colors ${isSortOpen ? 'bg-content/10' : 'bg-transparent hover:bg-content/10'}`}
          >
            <ArrowUpDown size={16} strokeWidth={1.5} className="text-content" />
          </button>
          
          {isSortOpen && (
            <div className="absolute top-full right-0 mt-1 w-48 bg-background border border-content shadow-none z-30">
              <div className="flex flex-col py-1">
                {[
                  { id: 'recent', label: 'Recent Activity' },
                  { id: 'name', label: 'Name' },
                  { id: 'status', label: 'Status' }
                ].map(option => (
                  <button
                    key={option.id}
                    onClick={() => {
                      setSort(option.id);
                      setIsSortOpen(false);
                    }}
                    className={`px-4 py-2 text-left font-mono text-[11px] uppercase tracking-widest font-bold rounded-none transition-colors ${
                      sort === option.id 
                        ? 'bg-content text-background' 
                        : 'text-content hover:bg-content/5'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <button className="flex items-center justify-center gap-2 bg-content text-background px-4 py-1.5 font-label-caps font-bold text-label-caps uppercase tracking-widest hover:bg-interactive transition-colors rounded-none border border-content shrink-0 shadow-none">
          <Plus className="w-4 h-4" />
          NEW CASE
        </button>
      </div>
    </div>
  );
}
