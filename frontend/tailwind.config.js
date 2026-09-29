/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cream: '#F6F7F2',
        ink: '#24261F',
        'ink-soft': '#6B6F63',
        forest: '#1F4D3A',
        'forest-dark': '#163726',
        gold: '#D9A441',
        'gold-soft': '#F3E3C0',
        line: '#E1E1D6',
      },
      fontFamily: {
        display: ['Fraunces', 'serif'],
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
