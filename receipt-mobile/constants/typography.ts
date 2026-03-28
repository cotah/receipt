import { TextStyle } from 'react-native';

export const Fonts = {
  display: 'DMSerifDisplay_400Regular',
  body: 'DMSans_400Regular',
  bodyMedium: 'DMSans_500Medium',
  bodySemiBold: 'DMSans_600SemiBold',
  bodyBold: 'DMSans_700Bold',
  mono: 'JetBrainsMono_600SemiBold',
  monoMedium: 'JetBrainsMono_500Medium',
  monoBold: 'JetBrainsMono_700Bold',
};

export const Typography: Record<string, TextStyle> = {
  displayLarge: { fontFamily: Fonts.display, fontSize: 32, lineHeight: 40 },
  displayMedium: { fontFamily: Fonts.display, fontSize: 24, lineHeight: 32 },
  displaySmall: { fontFamily: Fonts.display, fontSize: 20, lineHeight: 28 },
  headingLarge: { fontFamily: Fonts.bodyBold, fontSize: 20, lineHeight: 28 },
  headingMedium: { fontFamily: Fonts.bodySemiBold, fontSize: 18, lineHeight: 24 },
  headingSmall: { fontFamily: Fonts.bodySemiBold, fontSize: 16, lineHeight: 22 },
  bodyLarge: { fontFamily: Fonts.body, fontSize: 16, lineHeight: 24 },
  bodyMedium: { fontFamily: Fonts.body, fontSize: 14, lineHeight: 20 },
  bodySmall: { fontFamily: Fonts.body, fontSize: 12, lineHeight: 16 },
  price: { fontFamily: Fonts.mono, fontSize: 16, lineHeight: 22 },
  priceLarge: { fontFamily: Fonts.monoBold, fontSize: 24, lineHeight: 32 },
  priceSmall: { fontFamily: Fonts.monoMedium, fontSize: 12, lineHeight: 16 },
  caption: { fontFamily: Fonts.body, fontSize: 11, lineHeight: 14 },
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const BorderRadius = {
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
  full: 9999,
} as const;
