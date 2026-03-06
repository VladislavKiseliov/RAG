/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#1D3557',
        accent: '#457B9D',
        success: '#2D6A4F',
        warning: '#E9C46A',
        danger: '#E76F51',
        background: '#F8F9FA',
        surface: '#FFFFFF',
        text: '#1A1A2E',
        muted: '#6C757D',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
