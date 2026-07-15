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
        'space-black': '#0b0f19',
        'space-gray': '#162032',
        'space-gray-light': '#1e293b',
        'cyber-blue': '#38bdf8',
        'cyber-blue-dark': '#0284c7',
        'neon-green': '#4ade80',
        'neon-green-dark': '#16a34a',
        'amber-alert': '#f59e0b',
        'crimson-alert': '#f43f5e',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
