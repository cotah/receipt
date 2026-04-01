export const STORE_COLORS = {
  Lidl: { primary: '#F0997B', light: 'rgba(240,153,123,0.12)', text: '#FFFFFF' },
  Aldi: { primary: '#7C8CF0', light: 'rgba(124,140,240,0.12)', text: '#FFFFFF' },
  Tesco: { primary: '#85B7EB', light: 'rgba(133,183,235,0.12)', text: '#FFFFFF' },
  SuperValu: { primary: '#F0D68A', light: 'rgba(240,214,138,0.12)', text: '#FFFFFF' },
  Dunnes: { primary: '#5DCAA5', light: 'rgba(93,202,165,0.12)', text: '#FFFFFF' },
} as const;

export type StoreName = keyof typeof STORE_COLORS;
export const STORE_NAMES: StoreName[] = ['Lidl', 'Aldi', 'Tesco', 'SuperValu', 'Dunnes'];
