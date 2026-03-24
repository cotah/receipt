import { useRouter } from 'expo-router';
import { Gesture } from 'react-native-gesture-handler';

const TAB_ORDER = ['/(tabs)', '/(tabs)/history', '/(tabs)/prices', '/(tabs)/chat'] as const;

export function useTabSwipe(currentIndex: number) {
  const router = useRouter();

  const fling = Gesture.Pan()
    .activeOffsetX([-30, 30])
    .failOffsetY([-20, 20])
    .onEnd((event) => {
      const { velocityX, translationX } = event;
      if (Math.abs(translationX) < 50) return;

      if (translationX < 0 && velocityX < 0 && currentIndex < TAB_ORDER.length - 1) {
        // Swipe left → next tab
        router.replace(TAB_ORDER[currentIndex + 1]);
      } else if (translationX > 0 && velocityX > 0 && currentIndex > 0) {
        // Swipe right → previous tab
        router.replace(TAB_ORDER[currentIndex - 1]);
      }
    });

  return fling;
}
