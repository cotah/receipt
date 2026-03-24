import React from 'react';
import { View, Image, Text, StyleSheet } from 'react-native';
import { Tabs } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import AlertBadge from '../../components/alerts/AlertBadge';
import { useAlertStore } from '../../stores/alertStore';
import { useAuthStore } from '../../stores/authStore';

function ProfileTabIcon({ focused }: { focused: boolean }) {
  const profile = useAuthStore((s) => s.profile);
  const borderColor = focused ? Colors.primary.dark : Colors.text.tertiary;

  if (profile?.avatar_url) {
    return (
      <Image
        source={{ uri: profile.avatar_url }}
        style={[styles.profileIcon, { borderColor }]}
      />
    );
  }

  // Initials fallback
  const name = profile?.full_name;
  const initials = name
    ? name.split(/\s+/).map((w: string) => w[0]).join('').substring(0, 2).toUpperCase()
    : '?';

  return (
    <View style={[styles.profileIconFallback, { borderColor }]}>
      <Text style={[styles.profileInitials, { color: focused ? Colors.primary.dark : Colors.text.tertiary }]}>
        {initials}
      </Text>
    </View>
  );
}

export default function TabLayout() {
  const unreadCount = useAlertStore((s) => s.unreadCount);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: Colors.primary.dark,
        tabBarInactiveTintColor: Colors.text.tertiary,
        tabBarStyle: styles.tabBar,
        tabBarLabelStyle: styles.tabLabel,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => <Feather name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <Feather name="clock" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="scan"
        options={{
          title: '',
          tabBarIcon: () => (
            <View style={styles.scanBtn}>
              <Feather name="camera" size={24} color="#FFF" />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="prices"
        options={{
          title: 'Prices',
          tabBarIcon: ({ color, size }) => (
            <View>
              <Feather name="tag" size={size} color={color} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title: 'Chat',
          tabBarIcon: ({ color, size }) => (
            <View>
              <Feather name="message-circle" size={size} color={color} />
              <AlertBadge count={unreadCount} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ focused }) => <ProfileTabIcon focused={focused} />,
        }}
      />
      {/* Hide old settings route if file still exists */}
      <Tabs.Screen
        name="settings"
        options={{ href: null }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.surface.card,
    borderTopWidth: 0,
    height: 80,
    paddingBottom: 20,
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 4,
  },
  tabLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11 },
  scanBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.primary.default,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
    shadowColor: '#0D2B1D',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
  },
  profileIcon: {
    width: 26, height: 26, borderRadius: 13,
    borderWidth: 2,
  },
  profileIconFallback: {
    width: 26, height: 26, borderRadius: 13,
    borderWidth: 2,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: Colors.primary.pale,
  },
  profileInitials: {
    fontFamily: 'DMSans_700Bold', fontSize: 10,
  },
});
