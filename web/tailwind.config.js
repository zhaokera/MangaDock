/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 通用主题色
        'primary': '#6366F1',     // Indigo
        'secondary': '#EC4899',   // Pink
        'accent': '#10B981',      // Emerald

        // 平台特定色
        'bili-blue': '#00A1D6',
        'bili-pink': '#FB7299',
        'manhua-green': '#10B981',
        'manhua-light': '#34D399',
      },
      fontFamily: {
        display: ['ZCOOL KuaiLe', 'Noto Sans SC', 'sans-serif'],
        sans: ['Noto Sans SC', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      animation: {
        'float': 'float 3s ease-in-out infinite',
        'gradient': 'gradientShift 3s ease infinite',
        'shimmer': 'shimmer 1.5s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '50%': { transform: 'translateY(-10px) rotate(3deg)' },
        },
        gradientShift: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
}