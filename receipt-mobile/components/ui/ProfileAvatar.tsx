import React from 'react';
import { Image, View, Text, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors } from '../../constants/colors';
import { useAuthStore } from '../../stores/authStore';

interface Props {
  size?: number;
}

export default function ProfileAvatar({ size = 30 }: Props) {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const borderRadius = size / 2;

  const name = profile?.full_name;
  const initials = name
    ? name.split(/\s+/).map((w) => w[0]).join('').substring(0, 2).toUpperCase()
    : '?';

  return (
    <Pressable onPress={() => router.push('/(tabs)/profile')} hitSlop={12}>
      {profile?.avatar_url ? (
        <Image
          source={{ uri: profile.avatar_url }}
          style={[styles.img, { width: size, height: size, borderRadius }]}
        />
      ) : (
        <View style={[styles.fallback, { width: size, height: size, borderRadius }]}>
          <Text style={[styles.initials, { fontSize: size * 0.38 }]}>{initials}</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  img: {
    borderWidth: 2,
    borderColor: Colors.primary.default,
  },
  fallback: {
    backgroundColor: Colors.primary.default,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.primary.light,
  },
  initials: {
    fontFamily: 'DMSans_700Bold',
    color: '#FFF',
  },
});
