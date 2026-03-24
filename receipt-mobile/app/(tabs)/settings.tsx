import React from 'react';
import { View, Text, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';

export default function SettingsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const signOut = useAuthStore((s) => s.signOut);

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          await signOut();
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Button
          title=""
          variant="ghost"
          icon="arrow-left"
          onPress={() => router.back()}
          size="sm"
        />
        <Text style={styles.title}>Settings</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.content}>
        {/* Profile card */}
        <Card variant="elevated" style={styles.profileCard}>
          <View style={styles.avatar}>
            <Feather name="user" size={32} color={Colors.primary.default} />
          </View>
          <Text style={styles.name}>{profile?.full_name || 'User'}</Text>
          <Text style={styles.email}>{profile?.email || ''}</Text>
        </Card>

        {/* Preferences */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Preferences</Text>
          <Card style={styles.row}>
            <View style={styles.rowLeft}>
              <Feather name="bell" size={18} color={Colors.text.secondary} />
              <Text style={styles.rowLabel}>Notifications</Text>
            </View>
            <Text style={styles.rowValue}>{profile?.notify_alerts ? 'On' : 'Off'}</Text>
          </Card>
          <Card style={styles.row}>
            <View style={styles.rowLeft}>
              <Feather name="mail" size={18} color={Colors.text.secondary} />
              <Text style={styles.rowLabel}>Monthly Reports</Text>
            </View>
            <Text style={styles.rowValue}>{profile?.notify_reports ? 'On' : 'Off'}</Text>
          </Card>
          <Card style={styles.row}>
            <View style={styles.rowLeft}>
              <Feather name="map-pin" size={18} color={Colors.text.secondary} />
              <Text style={styles.rowLabel}>Home Area</Text>
            </View>
            <Text style={styles.rowValue}>{profile?.home_area || 'Not set'}</Text>
          </Card>
        </View>

        {/* Sign out */}
        <View style={styles.signOutSection}>
          <Button
            title="Sign Out"
            variant="secondary"
            icon="log-out"
            onPress={handleSignOut}
            fullWidth
          />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.sm,
  },
  title: {
    fontFamily: 'DMSerifDisplay_400Regular',
    fontSize: 22,
    color: Colors.primary.dark,
  },
  content: { flex: 1, paddingHorizontal: Spacing.md },
  profileCard: {
    alignItems: 'center',
    paddingVertical: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primary.pale,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  name: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 20,
    color: Colors.text.primary,
  },
  email: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    color: Colors.text.secondary,
    marginTop: 2,
  },
  section: { marginBottom: Spacing.lg },
  sectionTitle: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 16,
    color: Colors.text.primary,
    marginBottom: Spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.xs,
  },
  rowLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  rowLabel: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 15,
    color: Colors.text.primary,
  },
  rowValue: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    color: Colors.text.secondary,
  },
  signOutSection: { marginTop: 'auto', paddingBottom: Spacing.xl },
});
