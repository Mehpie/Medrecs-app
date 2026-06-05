import React, { useEffect, useRef } from 'react';

export default function GlobalReactiveGrid() {
  const containerRef = useRef(null);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!containerRef.current) return;

      const vw = window.innerWidth;
      const vh = window.innerHeight;
      
      const baseLeft = vw * 0.05;
      const baseTop = vh * 0.05;

      const parallaxX = e.clientX / -50;
      const parallaxY = e.clientY / -50;

      const relX = e.clientX + baseLeft - parallaxX;
      const relY = e.clientY + baseTop - parallaxY;

      // Update CSS variables directly for maximum performance (avoids layout thrashing)
      containerRef.current.style.setProperty('--mouse-x', `${relX}px`);
      containerRef.current.style.setProperty('--mouse-y', `${relY}px`);
      containerRef.current.style.setProperty('--parallax-x', `${parallaxX}px`);
      containerRef.current.style.setProperty('--parallax-y', `${parallaxY}px`);
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    
    // Set initial position
    handleMouseMove({ clientX: window.innerWidth / 2, clientY: window.innerHeight / 2 });
    
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div 
      ref={containerRef}
      className="fixed z-[-10] pointer-events-none text-content transform-gpu"
      style={{
        width: '110vw',
        height: '110vh',
        left: '-5vw',
        top: '-5vh',
        transform: 'translate3d(var(--parallax-x, 0), var(--parallax-y, 0), 0)',
        WebkitMaskImage: 'radial-gradient(400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(0,0,0,1) 0%, rgba(0,0,0,0.15) 100%)',
        maskImage: 'radial-gradient(400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(0,0,0,1) 0%, rgba(0,0,0,0.15) 100%)',
      }}
    >
      <svg className="w-full h-full opacity-30">
        <defs>
          <pattern id="dart-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect 
          width="200%" 
          height="200%" 
          x="-50%" 
          y="-50%" 
          fill="url(#dart-grid)" 
          className="animate-grid-drift"
        />
      </svg>
    </div>
  );
}
