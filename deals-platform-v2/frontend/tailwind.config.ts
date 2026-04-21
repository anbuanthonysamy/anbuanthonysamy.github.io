import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
      },
      colors: {
        brand: {
          orange: '#FD5108',
          'orange-dark': '#FD6412',
          'orange-light': '#FEB791',
        },
        neutral: {
          black: '#000000',
          'dark-bg': '#2D2D2D',
          'dark-secondary': '#464646',
          'dark-tertiary': '#7D7D7D',
          'light-tertiary': '#DEDEDE',
          white: '#FFFFFF',
        },
        data: {
          yellow: '#FFB600',
          'yellow-light': '#FFC83D',
          'yellow-lighter': '#FFECBD',
          red: '#E0301E',
          'red-light': '#E86153',
          'red-lighter': '#F7C8C4',
          rose: '#6E2A35',
          'rose-secondary': '#A43E50',
          'rose-tertiary': '#E27588',
          'rose-light': '#F1BAC3',
        },
        status: {
          ok: '#059669',
          warn: '#FFB600',
          risk: '#E0301E',
          mock: '#7c3aed',
        },
      },
    },
  },
  plugins: [],
};
export default config;
