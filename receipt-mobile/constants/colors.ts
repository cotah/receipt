// ─────────────────────────────────────────────
// SmartDocket — Liquid Glass Design Tokens
// Inspired by iOS 26 glassmorphism
// ─────────────────────────────────────────────

export const Colors = {
  // Deep green backgrounds (the "canvas")
  primary: {
    dark: '#0a1f14',
    default: '#0d2818',
    light: '#1a3a2a',
    pale: 'rgba(80,200,120,0.12)',
  },

  // Glass surfaces — translucent layers over dark backgrounds
  surface: {
    background: '#0d2818',
    card: 'rgba(255,255,255,0.08)',
    cardGlass: 'rgba(255,255,255,0.08)',
    cardBright: 'rgba(255,255,255,0.12)',
    cardAccent: 'rgba(80,200,120,0.12)',
    cardGold: 'rgba(212,168,67,0.10)',
    alt: 'rgba(255,255,255,0.04)',
    border: 'rgba(255,255,255,0.15)',
    borderSubtle: 'rgba(255,255,255,0.08)',
    borderBright: 'rgba(255,255,255,0.20)',
    elevated: 'rgba(255,255,255,0.12)',
  },

  // Accent colors — luminous, vibrant
  accent: {
    green: '#7DDFAA',
    greenSoft: 'rgba(80,200,120,0.15)',
    greenBorder: 'rgba(80,200,120,0.25)',
    greenBtn: 'rgba(80,200,120,0.20)',
    greenBtnBorder: 'rgba(80,200,120,0.30)',
    amber: '#F0D68A',
    amberSoft: 'rgba(212,168,67,0.12)',
    amberBorder: 'rgba(212,168,67,0.20)',
    red: '#F07B7B',
    redSoft: 'rgba(240,123,123,0.12)',
    blue: '#85B7EB',
    coral: '#F0997B',
    lilac: '#AFA9EC',
    lilacBright: '#7C8CF0',
  },

  // Text — white on dark
  text: {
    primary: '#FFFFFF',
    secondary: 'rgba(255,255,255,0.50)',
    tertiary: 'rgba(255,255,255,0.35)',
    inverse: '#FFFFFF',
    muted: 'rgba(255,255,255,0.25)',
  },

  // Glass effect constants
  glass: {
    highlight: 'rgba(255,255,255,0.06)',
    highlightEnd: 'transparent',
    specular: 'rgba(255,255,255,0.04)',
    borderThin: 0.5,
  },

  // Gradients
  gradient: {
    brand: ['#0d2818', '#1a3a2a'] as const,
    saving: ['#34D399', '#7DDFAA'] as const,
    amber: ['#F0D68A', '#D4A843'] as const,
    card: ['rgba(255,255,255,0.06)', 'transparent'] as const,
    hero: ['#0a1f14', '#1a3a2a'] as const,
    mesh: ['#0d2818', '#1a3a2a', '#0a1f14'] as const,
  },

  // Store glass fill colors (for price bars)
  storeGlass: {
    Tesco: 'rgba(133,183,235,0.30)',
    Lidl: 'rgba(240,153,123,0.35)',
    Aldi: 'rgba(124,140,240,0.40)',
    Dunnes: 'rgba(93,202,165,0.30)',
    SuperValu: 'rgba(240,214,138,0.30)',
  } as Record<string, string>,
};

export const Shadows = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 3,
  },
  cardHover: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.20,
    shadowRadius: 20,
    elevation: 5,
  },
  modal: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.30,
    shadowRadius: 40,
    elevation: 10,
  },
  float: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.20,
    shadowRadius: 20,
    elevation: 6,
  },
  glow: {
    shadowColor: '#7DDFAA',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
  glowGold: {
    shadowColor: '#F0D68A',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.20,
    shadowRadius: 12,
    elevation: 3,
  },
};
