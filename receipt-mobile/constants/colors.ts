export const Colors = {
  primary: {
    dark: '#0D2B1D',
    default: '#1A4D35',
    light: '#2E7D52',
    pale: '#E8F5EE',
  },
  surface: {
    background: '#F5F3EE',
    card: '#FFFFFF',
    cardGlass: 'rgba(255,255,255,0.85)',
    alt: '#EDEBE5',
    border: '#E0DDD6',
    elevated: '#FFFFFF',
  },
  accent: {
    green: '#3CB371',
    greenSoft: 'rgba(60,179,113,0.12)',
    amber: '#E8A020',
    amberSoft: 'rgba(232,160,32,0.12)',
    red: '#D94F4F',
    redSoft: 'rgba(217,79,79,0.10)',
    blue: '#2D6EA8',
  },
  text: {
    primary: '#1A1A1A',
    secondary: '#5A5F6B',
    tertiary: '#9CA3AF',
    inverse: '#FFFFFF',
  },
  gradient: {
    brand: ['#0D2B1D', '#1A6B42'] as const,
    saving: ['#34D399', '#22C55E'] as const,
    amber: ['#FBBF24', '#D97706'] as const,
    card: ['#FFFFFF', '#FAFAF7'] as const,
    hero: ['#0D2B1D', '#1A5438'] as const,
  },
};

export const Shadows = {
  card: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  cardHover: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 5,
  },
  modal: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.2,
    shadowRadius: 40,
    elevation: 10,
  },
  float: {
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.14,
    shadowRadius: 20,
    elevation: 6,
  },
  glow: {
    shadowColor: '#3CB371',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
};
