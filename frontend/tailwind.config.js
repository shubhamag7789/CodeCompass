/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          dark: '#0c101d',
          surface: 'rgba(18, 26, 48, 0.65)',
          card: 'rgba(22, 32, 58, 0.6)',
          cyan: '#38bdf8',
          blue: '#3b82f6',
          indigo: '#6366f1',
          purple: '#a855f7',
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};

