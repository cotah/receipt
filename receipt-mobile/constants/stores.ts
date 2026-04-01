// ─────────────────────────────────────────────
// Store colors — Liquid Glass variants
// Each store has: glass fill, glass border, accent text, and a logo tint
// ─────────────────────────────────────────────

export const STORE_COLORS = {
  Lidl: {
    primary: '#F0997B',
    light: 'rgba(240,153,123,0.15)',
    border: 'rgba(240,153,123,0.25)',
    text: '#F0997B',
    glass: 'rgba(240,153,123,0.35)',
  },
  Aldi: {
    primary: '#7C8CF0',
    light: 'rgba(124,140,240,0.15)',
    border: 'rgba(124,140,240,0.25)',
    text: '#7C8CF0',
    glass: 'rgba(124,140,240,0.40)',
  },
  Tesco: {
    primary: '#85B7EB',
    light: 'rgba(133,183,235,0.15)',
    border: 'rgba(133,183,235,0.25)',
    text: '#85B7EB',
    glass: 'rgba(133,183,235,0.30)',
  },
  SuperValu: {
    primary: '#F0D68A',
    light: 'rgba(240,214,138,0.15)',
    border: 'rgba(240,214,138,0.25)',
    text: '#F0D68A',
    glass: 'rgba(240,214,138,0.30)',
  },
  Dunnes: {
    primary: '#5DCAA5',
    light: 'rgba(93,202,165,0.15)',
    border: 'rgba(93,202,165,0.25)',
    text: '#5DCAA5',
    glass: 'rgba(93,202,165,0.30)',
  },
} as const;

export type StoreName = keyof typeof STORE_COLORS;
export const STORE_NAMES: StoreName[] = ['Lidl', 'Aldi', 'Tesco', 'SuperValu', 'Dunnes'];
