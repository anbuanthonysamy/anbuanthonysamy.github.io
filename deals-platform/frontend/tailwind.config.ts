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
        ink: {
          DEFAULT: '#0f172a',
          soft: '#334155',
          muted: '#64748b',
        },
        paper: '#f8fafc',
        hairline: '#e2e8f0',
        brand: '#1e40af',
        status: {
          ok: '#059669',
          warn: '#d97706',
          risk: '#b91c1c',
          mock: '#7c3aed',
        },
      },
    },
  },
  plugins: [],
};
export default config;
