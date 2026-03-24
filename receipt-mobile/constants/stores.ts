export const STORE_COLORS = {
  Lidl: { primary: '#0050AA', light: '#E6EEF9', text: '#FFFFFF' },
  Aldi: { primary: '#004B93', light: '#E5EEF8', text: '#FFFFFF' },
  Tesco: { primary: '#EE1C2E', light: '#FDECEE', text: '#FFFFFF' },
  SuperValu: { primary: '#E4002B', light: '#FDEAEE', text: '#FFFFFF' },
  Dunnes: { primary: '#231F20', light: '#EBEBEB', text: '#FFFFFF' },
} as const;

export type StoreName = keyof typeof STORE_COLORS;
export const STORE_NAMES: StoreName[] = ['Lidl', 'Aldi', 'Tesco', 'SuperValu', 'Dunnes'];
