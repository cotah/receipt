export const Colors = {
  primary: {
    dark: '#0D2B1D',
    default: '#1A4D35',
    light: '#2E7D52',
    pale: '#E8F5EE',
  },
  surface: {
    background: '#F7F5F0',
    card: '#FFFFFF',
    alt: '#F0EDE8',
    border: '#E5E2DC',
  },
  accent: {
    green: '#3CB371',
    amber: '#E8A020',
    red: '#D94F4F',
    blue: '#2D6EA8',
  },
  text: {
    primary: '#1A1A1A',
    secondary: '#6B7280',
    tertiary: '#9CA3AF',
    inverse: '#FFFFFF',
  },
  gradient: {
    brand: ['#0D2B1D', '#2E7D52'] as const,
    saving: ['#3CB371', '#2E7D52'] as const,
    amber: ['#E8A020', '#D4780A'] as const,
  },
};

export const Shadows = {
  card: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  modal: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 32,
    elevation: 8,
  },
  float: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 4,
  },
};
