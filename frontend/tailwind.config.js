/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--color-background) / <alpha-value>)',
        surface: {
          DEFAULT: 'rgb(var(--color-surface) / <alpha-value>)',
          muted: 'rgb(var(--color-surface-muted) / <alpha-value>)',
          elevated: 'rgb(var(--color-surface-elevated) / <alpha-value>)',
          border: 'rgb(var(--color-surface-border) / <alpha-value>)',
          'border-hover': 'rgb(var(--color-surface-border-hover) / <alpha-value>)',
        },
        primary: {
          DEFAULT: 'rgb(var(--color-primary) / <alpha-value>)',
          hover: 'rgb(var(--color-primary-hover) / <alpha-value>)',
          subtle: 'rgba(var(--color-primary) / 0.08)',
          border: 'rgba(var(--color-primary) / 0.25)',
        },
        accent: {
          orange: '#EA580C',
          amber: '#D97706',
          emerald: '#059669',
          rose: '#DC2626',
          dark: 'rgb(var(--color-accent-dark) / <alpha-value>)',
        },
        enterprise: {
          text: 'rgb(var(--color-enterprise-text) / <alpha-value>)',
          muted: 'rgb(var(--color-enterprise-muted) / <alpha-value>)',
          dim: 'rgb(var(--color-enterprise-dim) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        subtle: '0 2px 8px -2px rgba(0, 0, 0, 0.08), 0 1px 3px -1px rgba(0, 0, 0, 0.04)',
        paper: '0 4px 20px -2px rgba(0, 0, 0, 0.12)',
        warm: '0 0 35px -5px rgba(224, 90, 43, 0.16)',
      },
    },
  },
  plugins: [],
};
