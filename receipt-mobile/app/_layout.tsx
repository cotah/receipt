import React, { useEffect, useState, useRef } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import * as Linking from 'expo-linking';
import * as Notifications from 'expo-notifications';
import * as Sentry from '@sentry/react-native';
import * as SplashScreen from 'expo-splash-screen';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useAuthStore } from '../stores/authStore';
import { useAlertStore } from '../stores/alertStore';
import { registerForPushNotifications } from '../services/notifications';
import { configurePurchases, loginPurchases } from '../services/purchases';
import { ONBOARDING_KEY } from './onboarding';

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

Sentry.init({
  dsn: SENTRY_DSN,
  tracesSampleRate: 1.0,
  environment: __DEV__ ? 'development' : 'production',
  enabled: SENTRY_DSN.length > 0,
});

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    DMSerifDisplay_400Regular: require('../assets/fonts/DMSerifDisplay-Regular.ttf'),
    DMSans_400Regular: require('../assets/fonts/DMSans-Regular.ttf'),
    DMSans_500Medium: require('../assets/fonts/DMSans-Medium.ttf'),
    DMSans_600SemiBold: require('../assets/fonts/DMSans-SemiBold.ttf'),
    DMSans_700Bold: require('../assets/fonts/DMSans-Bold.ttf'),
    JetBrainsMono_500Medium: require('../assets/fonts/JetBrainsMono-Medium.ttf'),
    JetBrainsMono_600SemiBold: require('../assets/fonts/JetBrainsMono-SemiBold.ttf'),
    JetBrainsMono_700Bold: require('../assets/fonts/JetBrainsMono-Bold.ttf'),
  });

  const initialize = useAuthStore((s) => s.initialize);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const handleDeepLink = useAuthStore((s) => s.handleDeepLink);
  const segments = useSegments();
  const router = useRouter();
  const [hasSeenOnboarding, setHasSeenOnboarding] = useState<boolean | null>(null);

  useEffect(() => {
    initialize();
    // Check onboarding status — with fallback to prevent white screen
    AsyncStorage.getItem(ONBOARDING_KEY)
      .then((val) => {
        setHasSeenOnboarding(val === 'true');
      })
      .catch(() => {
        // If AsyncStorage fails, skip onboarding to prevent white screen
        setHasSeenOnboarding(true);
      });
    // Safety timeout: if AsyncStorage hangs, proceed after 2s
    const timeout = setTimeout(() => {
      setHasSeenOnboarding((prev) => prev === null ? true : prev);
    }, 2000);
    return () => clearTimeout(timeout);
  }, []);

  // Deep link listener — captures magic link redirects with auth tokens
  useEffect(() => {
    // URL that cold-started the app
    Linking.getInitialURL().then((url) => {
      if (url) handleDeepLink(url);
    });

    // URLs received while the app is already open
    const subscription = Linking.addEventListener('url', ({ url }) => {
      handleDeepLink(url);
    });

    return () => subscription.remove();
  }, []);

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  useEffect(() => {
    if (isLoading || !fontsLoaded || hasSeenOnboarding === null) return;

    const inAuthScreens = segments[0] === '(auth)';
    const inAuthCallback = segments[0] === 'auth'; // /auth/callback — deep link route
    const inOnboarding = segments[0] === 'onboarding';

    // First launch — show onboarding before anything else
    if (!hasSeenOnboarding && !inOnboarding) {
      // Re-check AsyncStorage in case onboarding just finished
      AsyncStorage.getItem(ONBOARDING_KEY).then((val) => {
        if (val === 'true') {
          setHasSeenOnboarding(true);
        } else {
          router.replace('/onboarding');
        }
      }).catch(() => {
        router.replace('/onboarding');
      });
      return;
    }

    if (!isAuthenticated && !inAuthScreens && !inAuthCallback && !inOnboarding) {
      router.replace('/(auth)/login');
    } else if (isAuthenticated && (inAuthScreens || inAuthCallback)) {
      router.replace('/(tabs)');
    }
  }, [isAuthenticated, isLoading, fontsLoaded, segments, hasSeenOnboarding]);

  // Register for push notifications + init RevenueCat when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      registerForPushNotifications().catch(() => {});
      // Initialize RevenueCat for In-App Purchases
      const userId = useAuthStore.getState().user?.id;
      configurePurchases(userId).then(() => {
        if (userId) loginPurchases(userId);
      }).catch(() => {});
    }
  }, [isAuthenticated]);

  // Push notification listeners — handle tap navigation + refresh alerts
  useEffect(() => {
    if (!isAuthenticated) return;

    // When user TAPS a push notification → navigate to the right screen
    const responseSub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as Record<string, any> | undefined;
      if (!data?.screen) return;

      // Map screen names from backend to app routes
      switch (data.screen) {
        case 'offers':
        case 'prices':
          router.push('/(tabs)/prices');
          break;
        case 'alerts':
          router.push('/alerts');
          break;
        default:
          router.push('/(tabs)');
      }
    });

    // When notification arrives while app is OPEN → refresh the bell badge
    const receivedSub = Notifications.addNotificationReceivedListener(() => {
      useAlertStore.getState().fetchAlerts();
    });

    return () => {
      responseSub.remove();
      receivedSub.remove();
    };
  }, [isAuthenticated, router]);

  if (!fontsLoaded || isLoading || hasSeenOnboarding === null) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, animation: 'slide_from_right' }} />
    </GestureHandlerRootView>
  );
}
