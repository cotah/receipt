import { useEffect } from 'react';
import { View, ActivityIndicator, Text, StyleSheet } from 'react-native';
import { useURL } from 'expo-linking';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../stores/authStore';
import { Colors } from '../../constants/colors';

export default function AuthCallbackScreen() {
  const url = useURL();
  const router = useRouter();
  const handleDeepLink = useAuthStore((s) => s.handleDeepLink);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (url) {
      handleDeepLink(url);
    }
  }, [url]);

  // Once authenticated, navigate to main app
  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/(tabs)');
    }
  }, [isAuthenticated]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color={Colors.primary.default} />
      <Text style={styles.text}>Signing you in...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.surface.background,
    gap: 16,
  },
  text: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 16,
    color: Colors.text.secondary,
  },
});
