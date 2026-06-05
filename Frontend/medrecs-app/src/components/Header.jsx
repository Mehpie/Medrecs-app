import React, { useState, useRef, useEffect } from 'react';
import { Search, Moon, Sun, Bell, Terminal } from 'lucide-react';
import { useTheme } from '../ThemeContext';

const NOTIFICATIONS = [
  { id: 1, text: "Output generated for DART-8821", time: "10:42 AM", unread: true, type: "success" },
  { id: 2, text: "Telemetry sync failed on Node 4", time: "09:15 AM", unread: true, type: "pending" },
  { id: 3, text: "Archive request completed for INT-2024", time: "YESTERDAY", unread: false, type: "neutral" },
];

export default function Header({ searchQuery, setSearchQuery }) {
  const { isDark, toggleTheme } = useTheme();
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const notifRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setIsNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="w-full border-b border-content bg-background flex justify-between items-center px-6 md:px-10 h-16 shrink-0 transition-colors duration-200">
      <div className="flex items-center gap-4">
        <span className="font-sans font-bold tracking-widest text-content">LUMINA OS</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative hidden sm:block">
          <Search size={16} className="absolute left-0 top-1/2 -translate-y-1/2 text-content/50" />
          <input
            className="pl-7 pr-4 py-1.5 border-b border-content/30 bg-transparent text-content focus:border-content focus:outline-none focus:ring-0 font-mono text-sm w-64 placeholder:text-content/50 transition-colors rounded-none"
            placeholder="Search ledger..."
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 border-l border-content/20 pl-4 ml-2">
          <button 
            onClick={toggleTheme}
            className="w-9 h-9 flex items-center justify-center rounded-none text-content/70 bg-transparent hover:text-content hover:bg-content/10 transition-colors"
            title="Toggle Theme"
          >
            {isDark ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
          </button>
          
          <div className="relative flex items-center" ref={notifRef}>
            <button 
              onClick={() => setIsNotifOpen(!isNotifOpen)}
              className={`w-9 h-9 flex items-center justify-center rounded-none transition-colors ${isNotifOpen ? 'bg-content/10 text-content' : 'text-content/70 bg-transparent hover:text-content hover:bg-content/10'}`}
            >
              <Bell size={18} strokeWidth={1.5} />
            </button>

            {isNotifOpen && (
              <div 
                className="absolute right-0 top-12 w-80 bg-background border-2 border-content z-50 flex flex-col"
                style={{ boxShadow: '6px 6px 0px 0px rgb(var(--color-content))' }}
              >
                <div className="px-4 py-3 border-b border-content/20 flex items-center justify-between bg-background">
                  <span className="font-mono text-[11px] uppercase tracking-widest font-bold text-content">SYSTEM ALERTS</span>
                </div>
                <div className="flex flex-col max-h-96 overflow-y-auto bg-background">
                  {NOTIFICATIONS.map((n) => (
                    <div key={n.id} className="flex gap-3 p-4 border-b border-content/10 last:border-0 hover:bg-content/5 transition-colors cursor-pointer group">
                      <div className="pt-1.5 shrink-0 flex justify-center w-2">
                        {n.unread && (
                          <div className={`w-1.5 h-1.5 rounded-none ${n.type === 'success' ? 'bg-success' : 'bg-pending'}`}></div>
                        )}
                      </div>
                      <div className="flex flex-col gap-1 flex-1">
                        <span className="font-sans text-sm leading-tight text-content">{n.text}</span>
                        <span className="font-mono text-xs tabular-nums text-content/60 text-right w-full">{n.time}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button className="w-9 h-9 flex items-center justify-center rounded-none text-content/70 bg-transparent hover:text-content hover:bg-content/10 transition-colors">
            <Terminal size={18} strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </header>
  );
}
