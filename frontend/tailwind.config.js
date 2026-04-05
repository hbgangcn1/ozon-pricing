/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        zinc: {
          50: '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          900: '#18181b',
          950: '#09090b',
        },
        indigo: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
        },
        surface: { DEFAULT: '#0d1117', container: '#161b22', high: '#21262d', highest: '#30363d', bright: '#484f58' },
        primary: { DEFAULT: '#3e65ff', dim: '#718bff', container: '#1a237e' },
        cost: { product: '#FF6B6B', profit: '#34D399', logistics: '#FB923C', commission: '#C084FC', agent: '#98D8C8', promo: '#F7DC6F', payment: '#F8B739', return: '#EB984E', withdraw: '#85C1E9' },
        'text-primary': '#f1f3fc',
        'text-secondary': '#a8abb3',
        'text-muted': '#72757d',
        status: { success: '#34D399', error: '#F87171', warning: '#FACC15', info: '#60A5FA' },
      },
      fontFamily: {
        headline: ['Manrope', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}