import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Tabs } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import AlertBadge from '../../components/alerts/AlertBadge';
import { useAlertStore } from '../../stores/alertStore';

export default function TabLayout() {
  const unreadCount = useAlertStore((s) => s.unreadCount);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#7DDFAA',
        tabBarInactiveTintColor: 'rgba(255,255,255,0.35)',
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
              <Feather name="camera" size={24} color="#7DDFAA" />
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
      {/* Profile accessible via Home header icon, not tab bar */}
      <Tabs.Screen name="profile" options={{ href: null, tabBarStyle: { display: 'none' } }} />
      <Tabs.Screen name="settings" options={{ href: null, tabBarStyle: { display: 'none' } }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: 'rgba(13,40,24,0.95)',
    borderTopWidth: 0.5,
    borderTopColor: 'rgba(255,255,255,0.08)',
    height: 88,
    paddingBottom: 24,
    paddingTop: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 6,
  },
  tabLabel: { fontFamily: 'DMSans_600SemiBold', fontSize: 10, marginTop: 2 },
  scanBtn: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: 'rgba(80,200,120,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 28,
    shadowColor: '#7DDFAA',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 8,
    borderWidth: 0.5,
    borderColor: 'rgba(80,200,120,0.35)',
  },
});
