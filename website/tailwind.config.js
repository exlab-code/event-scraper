/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,js,svelte,ts}', './public/index.html', './src/**/*.svelte'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eef5ff',
          100: '#d9e8ff',
          200: '#bbd8ff',
          300: '#8bc1ff',
          400: '#549eff',
          500: '#3178ff',
          600: '#2361ff',
          700: '#194aec',
          800: '#1a3dd1',
          900: '#1c36a7',
          950: '#162163',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
