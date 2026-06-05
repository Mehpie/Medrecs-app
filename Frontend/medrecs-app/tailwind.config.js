/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--color-background) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        content: "rgb(var(--color-content) / <alpha-value>)",
        interactive: "#2D3748",
        success: "rgb(var(--color-success) / <alpha-value>)",
        pending: "rgb(var(--color-pending) / <alpha-value>)"
      },
      fontFamily: {
        "body-main": ["Inter", "sans-serif"],
        "headline-md": ["Inter", "sans-serif"],
        "label-caps": ["Inter", "sans-serif"],
        "data-lg": ["IBM Plex Mono", "monospace"],
        "display-xl-mobile": ["Inter", "sans-serif"],
        "display-xl": ["Inter", "sans-serif"],
        "data-sm": ["IBM Plex Mono", "monospace"],
        "display-lg": ["Inter", "sans-serif"]
      },
      keyframes: {
        'grid-drift': {
          '0%': { transform: 'translate(0, 0)' },
          '100%': { transform: 'translate(-40px, -40px)' },
        }
      },
      animation: {
        'grid-drift': 'grid-drift 25s linear infinite',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ],
}
