import React, { useEffect, useRef } from 'react';

const lensSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">
  <defs>
    <radialGradient id="grad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#808080" />
    </radialGradient>
  </defs>
  <rect width="400" height="400" fill="#808080" />
  <circle cx="200" cy="200" r="200" fill="url(#grad)" />
</svg>
`;
const lensDataUri = `data:image/svg+xml;utf8,${encodeURIComponent(lensSvg.trim())}`;

export default function GlobalReactiveGrid() {
  const containerRef = useRef(null);
  const offsetRef = useRef(null);

  const targetPos = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
  const currentPos = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
  const rafId = useRef(null);

  useEffect(() => {
    const handleMouseMove = (e) => {
      targetPos.current = { x: e.clientX, y: e.clientY };
    };

    const renderLoop = () => {
      // Lerp for buttery smooth spring physics
      currentPos.current.x += (targetPos.current.x - currentPos.current.x) * 0.15;
      currentPos.current.y += (targetPos.current.y - currentPos.current.y) * 0.15;

      const { x: clientX, y: clientY } = currentPos.current;

      if (containerRef.current) {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        
        // The container is slightly larger and offset to allow parallax without exposing edges
        const baseLeft = vw * 0.05;
        const baseTop = vh * 0.05;

        const parallaxX = clientX / -50;
        const parallaxY = clientY / -50;

        // Mouse position relative to the moving container's coordinate system
        const relX = clientX + baseLeft - parallaxX;
        const relY = clientY + baseTop - parallaxY;

        // 1. Proximity Mask (Flashlight effect)
        const maskStr = `radial-gradient(400px circle at ${relX}px ${relY}px, rgba(0,0,0,1) 0%, rgba(0,0,0,0.15) 100%)`;
        containerRef.current.style.maskImage = maskStr;
        containerRef.current.style.WebkitMaskImage = maskStr;
        
        // 2. Micro-Parallax (translate3d forces hardware acceleration)
        containerRef.current.style.transform = `translate3d(${parallaxX}px, ${parallaxY}px, 0)`;

        // 3. Coordinate Distortion Map Center
        if (offsetRef.current) {
          offsetRef.current.setAttribute('dx', relX - 200);
          offsetRef.current.setAttribute('dy', relY - 200);
        }
      }

      rafId.current = requestAnimationFrame(renderLoop);
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    
    // Start the animation loop
    rafId.current = requestAnimationFrame(renderLoop);
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, []);

  return (
    <>
      {/* SVG Filter Definition for the Lens Distortion */}
      <svg className="w-0 h-0 absolute pointer-events-none">
        <defs>
          <filter id="reactive-lens" x="-20vw" y="-20vh" width="140vw" height="140vh" colorInterpolationFilters="sRGB">
            <feImage href={lensDataUri} result="map" />
            <feOffset ref={offsetRef} dx="0" dy="0" in="map" result="movedMap" />
            {/* The displacement scale controls the severity of the distortion curve */}
            <feDisplacementMap in="SourceGraphic" in2="movedMap" scale="40" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
      </svg>

      {/* Reactive Grid Container */}
      <div 
        ref={containerRef}
        className="fixed z-[-10] pointer-events-none text-content"
        style={{
          width: '110vw',
          height: '110vh',
          left: '-5vw',
          top: '-5vh',
          filter: 'url(#reactive-lens)',
          WebkitMaskImage: 'radial-gradient(400px circle at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0.15) 100%)',
          maskImage: 'radial-gradient(400px circle at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0.15) 100%)',
        }}
      >
        <svg className="w-full h-full opacity-30">
          <defs>
            {/* Base inline SVG pattern for perfectly crisp 1px lines */}
            <pattern id="dart-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="1" />
            </pattern>
          </defs>
          {/* 
            The rect is large enough to overflow completely and is animated infinitely via CSS. 
            Moving exactly 40px over 25 seconds perfectly loops the 40px pattern without stuttering. 
          */}
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
    </>
  );
}
