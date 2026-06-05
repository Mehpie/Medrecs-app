import React, { useState } from 'react';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import GlobalReactiveGrid from './components/GlobalReactiveGrid';

function App() {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <div className="min-h-screen flex flex-col font-body-main text-body-main antialiased relative bg-transparent text-content transition-colors duration-200">
      <GlobalReactiveGrid />
      
      {/* Fixed DART Logo Anchor */}
      <div className="fixed bottom-10 left-10 z-50 pointer-events-none hidden md:block">
        <span className="font-headline-md text-headline-md tracking-tighter text-content opacity-30">
          ►DART
        </span>
      </div>

      <Header searchQuery={searchQuery} setSearchQuery={setSearchQuery} />
      
      <main className="flex-grow w-full max-w-[1440px] mx-auto px-6 md:px-10 py-12 md:py-16 flex flex-col gap-8">
        <Dashboard searchQuery={searchQuery} />
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-content bg-background flex flex-col md:flex-row justify-between items-center px-10 py-4 mt-auto">
        <div className="font-label-caps text-label-caps text-content opacity-70">
          © 2024 DEEP-TECH INSTITUTIONAL. ALL RIGHTS RESERVED.
        </div>
        <div className="flex gap-6 font-label-caps text-label-caps text-content opacity-70 mt-4 md:mt-0">
          <a className="hover:text-interactive hover:opacity-100 underline transition-colors" href="#">Privacy Protocol</a>
          <a className="hover:text-interactive hover:opacity-100 underline transition-colors" href="#">Security Audit</a>
          <a className="hover:text-interactive hover:opacity-100 underline transition-colors" href="#">API Docs</a>
        </div>
      </footer>
    </div>
  );
}

export default App;
