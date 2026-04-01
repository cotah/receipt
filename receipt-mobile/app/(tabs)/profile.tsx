import React, { useState } from 'react';
import { View, Text, StyleSheet, Alert, Switch, Pressable, Image, TextInput, ScrollView, Share, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import * as Linking from 'expo-linking';

import Card from '../../components/ui/Card';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import { supabase } from '../../services/supabase';

function getInitials(name: string | null | undefined): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return parts[0][0]?.toUpperCase() ?? '?';
}

function getLevel(points: number): { label: string; emoji: string } {
  if (points >= 500) return { label: 'Smart Shopper', emoji: '⭐' };
  if (points >= 100) return { label: 'Saver', emoji: '💚' };
  return { label: 'Starter', emoji: '🌱' };
}

export default function ProfileScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const user = useAuthStore((s) => s.user);
  const signOut = useAuthStore((s) => s.signOut);
  const setProfile = useAuthStore((s) => s.setProfile);

  const [showUpgrade, setShowUpgrade] = useState(false);
  const [editingArea, setEditingArea] = useState(false);
  const [areaText, setAreaText] = useState(profile?.home_area ?? '');
  const [editingName, setEditingName] = useState(false);
  const [nameText, setNameText] = useState(profile?.full_name ?? '');
  const [uploading, setUploading] = useState(false);

  const updateProfile = async (updates: Record<string, unknown>) => {
    if (!profile) return;
    const { error } = await supabase
      .from('profiles')
      .update(updates)
      .eq('id', profile.id);
    if (error) {
      console.error('Profile update failed:', error.message);
      return;
    }
    setProfile({ ...profile, ...updates } as typeof profile);
  };

  const handleToggleNotifications = (value: boolean) => {
    updateProfile({ notify_alerts: value });
  };

  const handleToggleReports = (value: boolean) => {
    updateProfile({ notify_reports: value });
  };

  const handleSaveArea = () => {
    updateProfile({ home_area: areaText.trim() || null });
    setEditingArea(false);
  };

  const handleSaveName = () => {
    updateProfile({ full_name: nameText.trim() || null });
    setEditingName(false);
  };

  const handlePickAvatar = async () => {
    if (!profile?.id) return;

    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Please allow photo access in Settings to change your avatar.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.3,
      });

      if (result.canceled || !result.assets[0]) return;

      setUploading(true);
      const asset = result.assets[0];

      // Resize to 200x200 by re-picking with small dimensions
      const base64 = await FileSystem.readAsStringAsync(asset.uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Store as data URI directly in profiles table
      const avatar_url = `data:image/jpeg;base64,${base64}`;
      await updateProfile({ avatar_url });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      console.error('Avatar upload failed:', msg, e);
      Alert.alert('Upload failed', msg);
    } finally {
      setUploading(false);
    }
  };

  const handleReferFriend = async () => {
    const code = profile?.referral_code || 'SMART';
    const baseUrl = process.env.EXPO_PUBLIC_API_URL?.replace('/api/v1', '') || '';
    try {
      await Share.share({
        message:
          `Join me on SmartDocket — the smart way to save on groceries in Ireland! 🛒\n\n` +
          `Use my code ${code} and we both get 50 bonus points.\n\n` +
          `Download: ${baseUrl}/admin/invite.html?ref=${code}`,
      });
    } catch {
      // User cancelled
    }
  };

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          try {
            await signOut();
          } catch (e) {
            console.error('Sign out error:', e);
          }
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  const initials = getInitials(profile?.full_name);
  const points = profile?.points ?? 0;
  const level = getLevel(points);
  const isPro = profile?.plan === 'pro';

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Back button */}
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Profile</Text>
        </Pressable>

        {/* Profile header */}
        <View style={styles.profileHeader}>
          <Pressable onPress={handlePickAvatar} style={styles.avatarWrap}>
            {profile?.avatar_url ? (
              <Image source={{ uri: profile.avatar_url }} style={styles.avatarImg} />
            ) : (
              <View style={styles.avatarFallback}>
                <Text style={styles.avatarInitials}>{initials}</Text>
              </View>
            )}
            <View style={styles.editBadge}>
              <Feather name="camera" size={14} color="#FFF" />
            </View>
          </Pressable>
          {uploading && <Text style={styles.uploadingText}>Uploading...</Text>}
          <Text style={styles.profileName}>{profile?.full_name?.split(' ')[0] || 'User'}</Text>
          <Text style={styles.profileEmail}>{user?.email || profile?.email || ''}</Text>
        </View>

        {/* Account section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>ACCOUNT</Text>
          <Card variant="elevated" style={styles.sectionCard}>
            {/* Name */}
            <Pressable
              style={styles.row}
              onPress={() => { setNameText(profile?.full_name ?? ''); setEditingName(true); }}
            >
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="user" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Name</Text>
              </View>
              {editingName ? (
                <View style={styles.inlineEdit}>
                  <TextInput
                    value={nameText}
                    onChangeText={setNameText}
                    placeholder="Your name"
                    style={styles.textInput}
                    autoFocus
                    onSubmitEditing={handleSaveName}
                    returnKeyType="done"
                  />
                  <Pressable onPress={handleSaveName} hitSlop={8}>
                    <Feather name="check" size={16} color={Colors.accent.green} />
                  </Pressable>
                </View>
              ) : (
                <View style={styles.rowRight}>
                  <Text style={styles.rowValue}>{profile?.full_name || 'Not set'}</Text>
                  <Feather name="chevron-right" size={16} color={Colors.text.tertiary} />
                </View>
              )}
            </Pressable>

            <View style={styles.divider} />

            {/* Email */}
            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="mail" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Email</Text>
              </View>
              <Text style={styles.rowValueMuted}>{user?.email || profile?.email || ''}</Text>
            </View>

            <View style={styles.divider} />

            {/* Home Area */}
            <Pressable
              style={styles.row}
              onPress={() => { setAreaText(profile?.home_area ?? ''); setEditingArea(true); }}
            >
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="map-pin" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Home Area</Text>
              </View>
              {editingArea ? (
                <View style={styles.inlineEdit}>
                  <TextInput
                    value={areaText}
                    onChangeText={setAreaText}
                    placeholder="e.g. Dublin 2"
                    style={styles.textInput}
                    autoFocus
                    onSubmitEditing={handleSaveArea}
                    returnKeyType="done"
                  />
                  <Pressable onPress={handleSaveArea} hitSlop={8}>
                    <Feather name="check" size={16} color={Colors.accent.green} />
                  </Pressable>
                </View>
              ) : (
                <View style={styles.rowRight}>
                  <Text style={styles.rowValue}>{profile?.home_area || 'Not set'}</Text>
                  <Feather name="chevron-right" size={16} color={Colors.text.tertiary} />
                </View>
              )}
            </Pressable>
          </Card>
        </View>

        {/* Preferences section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>PREFERENCES</Text>
          <Card variant="elevated" style={styles.sectionCard}>
            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="bell" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Notifications</Text>
              </View>
              <Switch
                value={profile?.notify_alerts ?? true}
                onValueChange={handleToggleNotifications}
                trackColor={{ false: 'rgba(255,255,255,0.12)', true: 'rgba(80,200,120,0.12)' }}
                thumbColor={(profile?.notify_alerts ?? true) ? Colors.primary.default : '#ccc'}
              />
            </View>

            <View style={styles.divider} />

            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="bar-chart-2" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Monthly Reports</Text>
              </View>
              <Switch
                value={profile?.notify_reports ?? true}
                onValueChange={handleToggleReports}
                trackColor={{ false: 'rgba(255,255,255,0.12)', true: 'rgba(80,200,120,0.12)' }}
                thumbColor={(profile?.notify_reports ?? true) ? Colors.primary.default : '#ccc'}
              />
            </View>
          </Card>
        </View>

        {/* Plan + Rewards section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>PLAN & REWARDS</Text>
          <Card variant="elevated" style={styles.sectionCard}>
            {/* Plan */}
            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="zap" size={16} color={isPro ? Colors.accent.amber : Colors.text.secondary} />
                </View>
                <View>
                  <Text style={styles.rowLabel}>{isPro ? 'Pro Plan' : 'Free Plan'}</Text>
                  <Text style={styles.rowHint}>
                    {isPro ? 'Unlimited scans & AI' : '10 scans/month, 5 AI queries/day'}
                  </Text>
                </View>
              </View>
              {isPro ? (
                <View style={styles.proBadge}>
                  <Text style={styles.proBadgeText}>Pro ⭐</Text>
                </View>
              ) : (
                <Pressable
                  style={styles.upgradeBtn}
                  onPress={() => setShowUpgrade(true)}
                >
                  <Text style={styles.upgradeBtnText}>Upgrade to Pro</Text>
                </Pressable>
              )}
            </View>

            <View style={styles.divider} />

            {/* Points */}
            <Pressable style={styles.row} onPress={() => router.push('/rewards')}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="star" size={16} color={Colors.accent.amber} />
                </View>
                <Text style={styles.rowLabel}>Points & Rewards</Text>
              </View>
              <View style={styles.rowRight}>
                <Text style={styles.rowValueBold}>{points}</Text>
                <Feather name="chevron-right" size={16} color={Colors.text.tertiary} />
              </View>
            </Pressable>

            <View style={styles.divider} />

            {/* Level */}
            <Pressable style={styles.row} onPress={() => router.push('/levels')}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="award" size={16} color={Colors.accent.amber} />
                </View>
                <Text style={styles.rowLabel}>Level</Text>
              </View>
              <View style={styles.rowRight}>
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{level.label} {level.emoji}</Text>
                </View>
                <Feather name="chevron-right" size={16} color={Colors.text.tertiary} />
              </View>
            </Pressable>

            <View style={styles.divider} />

            {/* Refer */}
            <Pressable style={styles.row} onPress={() => router.push('/refer')}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="gift" size={16} color={Colors.accent.green} />
                </View>
                <Text style={styles.rowLabel}>Refer a Friend 🎁</Text>
              </View>
              <View style={styles.rowRight}>
                <Text style={styles.rowValueAccent}>Share link</Text>
                <Feather name="chevron-right" size={16} color={Colors.accent.green} />
              </View>
            </Pressable>
          </Card>
        </View>

        {/* Report an Issue */}
        <Pressable
          style={styles.reportBtn}
          onPress={() => router.push('/feedback')}
        >
          <Feather name="alert-circle" size={18} color={Colors.accent.green} />
          <Text style={styles.reportText}>Report an Issue</Text>
        </Pressable>

        {/* Sign out */}
        <Pressable style={styles.signOutBtn} onPress={handleSignOut}>
          <Feather name="log-out" size={18} color="#DC3545" />
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </ScrollView>

      {/* Upgrade Modal */}
      <Modal visible={showUpgrade} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Choose your plan</Text>

            <View style={styles.plansRow}>
              {/* Free */}
              <View style={styles.planCard}>
                <Text style={styles.planName}>Free</Text>
                <Text style={styles.planPrice}>€0</Text>
                <Text style={styles.planPeriod}>/month</Text>
                {['10 scans/month', '30-day history', 'Weekly offers', 'Collective prices', '5 AI queries/day'].map((f) => (
                  <Text key={f} style={styles.planFeature}>✓ {f}</Text>
                ))}
                <Pressable style={styles.freeBtn} onPress={() => setShowUpgrade(false)}>
                  <Text style={styles.freeBtnText}>Upgrade</Text>
                </Pressable>
              </View>

              {/* Pro */}
              <View style={[styles.planCard, styles.planCardPro]}>
                <View style={styles.popularTag}><Text style={styles.popularTagText}>POPULAR</Text></View>
                <Text style={[styles.planName, { color: '#FFF' }]}>Pro</Text>
                <Text style={[styles.planPrice, { color: '#FFF' }]}>€4.99</Text>
                <Text style={[styles.planPeriod, { color: 'rgba(255,255,255,0.7)' }]}>/month</Text>
                {['Unlimited scans', 'Full history', 'Price alerts', 'Store comparison', 'Monthly email report', 'Unlimited AI chat', 'Trends analysis', 'Data export'].map((f) => (
                  <Text key={f} style={[styles.planFeature, { color: 'rgba(255,255,255,0.9)' }]}>✓ {f}</Text>
                ))}
                <Pressable
                  style={styles.proBtn}
                  onPress={() => {
                    setShowUpgrade(false);
                    Linking.openURL('https://receipt-production-ebc4.up.railway.app/admin/pro.html');
                  }}
                >
                  <Text style={styles.proBtnText}>Upgrade</Text>
                </Pressable>
              </View>
            </View>

            <Pressable onPress={() => setShowUpgrade(false)} style={styles.modalClose}>
              <Feather name="x" size={22} color={Colors.text.secondary} />
            </Pressable>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: Spacing.md, paddingVertical: 4 },
  backText: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: '#FFFFFF' },
  scroll: { paddingHorizontal: Spacing.md, paddingBottom: 40 },

  // Profile header
  profileHeader: { alignItems: 'center', paddingVertical: Spacing.lg },
  avatarWrap: { position: 'relative', marginBottom: Spacing.sm },
  avatarImg: {
    width: 100, height: 100, borderRadius: 50,
    borderWidth: 3, borderColor: Colors.primary.default,
  },
  avatarFallback: {
    width: 100, height: 100, borderRadius: 50,
    backgroundColor: 'rgba(80,200,120,0.20)',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 3, borderColor: Colors.primary.light,
  },
  avatarInitials: {
    fontFamily: 'DMSans_700Bold', fontSize: 36, color: '#FFF',
  },
  editBadge: {
    position: 'absolute', bottom: 2, right: 2,
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: 'rgba(80,200,120,0.20)',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.15)',
  },
  uploadingText: {
    fontFamily: 'DMSans_400Regular', fontSize: 12,
    color: Colors.text.tertiary, marginBottom: 4,
  },
  profileName: {
    fontFamily: 'DMSans_700Bold', fontSize: 22,
    color: Colors.text.primary,
  },
  profileEmail: {
    fontFamily: 'DMSans_400Regular', fontSize: 14,
    color: Colors.text.secondary, marginTop: 2,
  },

  // Sections
  section: { marginBottom: Spacing.lg },
  sectionLabel: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 12,
    color: Colors.text.tertiary, letterSpacing: 1,
    marginBottom: Spacing.sm, marginLeft: 4,
  },
  sectionCard: { padding: 0, overflow: 'hidden' },

  // Rows
  row: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14, paddingHorizontal: Spacing.md,
  },
  rowLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  iconCircle: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(80,200,120,0.12)',
    alignItems: 'center', justifyContent: 'center',
  },
  rowLabel: {
    fontFamily: 'DMSans_500Medium', fontSize: 15,
    color: Colors.text.primary,
  },
  rowValue: {
    fontFamily: 'DMSans_400Regular', fontSize: 14,
    color: Colors.text.secondary,
  },
  rowValueMuted: {
    fontFamily: 'DMSans_400Regular', fontSize: 14,
    color: Colors.text.tertiary,
  },
  rowValueBold: {
    fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16,
    color: Colors.text.primary,
  },
  rowValueAccent: {
    fontFamily: 'DMSans_500Medium', fontSize: 14,
    color: Colors.accent.green,
  },
  divider: { height: 1, backgroundColor: Colors.surface.alt, marginHorizontal: Spacing.md },
  rowHint: {
    fontFamily: 'DMSans_400Regular', fontSize: 11,
    color: Colors.text.tertiary, marginTop: 1,
  },
  proBadge: {
    backgroundColor: Colors.accent.amber + '20',
    paddingHorizontal: 12, paddingVertical: 5, borderRadius: 14,
  },
  proBadgeText: {
    fontFamily: 'DMSans_700Bold', fontSize: 13, color: Colors.accent.amber,
  },
  upgradeBtn: {
    backgroundColor: 'rgba(80,200,120,0.20)',
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10,
  },
  upgradeBtnText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: '#FFF',
  },

  // Inline editing
  inlineEdit: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  textInput: {
    fontFamily: 'DMSans_400Regular', fontSize: 14,
    color: Colors.text.primary, borderBottomWidth: 1,
    borderBottomColor: Colors.primary.default,
    minWidth: 100, paddingVertical: 2,
  },

  // Badge
  badge: {
    backgroundColor: Colors.accent.amber + '20',
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12,
  },
  badgeText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 12,
    color: Colors.accent.amber,
  },

  // Upgrade Modal
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center', alignItems: 'center', padding: 16,
  },
  modalContent: {
    backgroundColor: Colors.surface.background, borderRadius: 20,
    padding: 20, width: '100%', maxWidth: 400, position: 'relative',
  },
  modalTitle: {
    fontFamily: 'DMSans_700Bold', fontSize: 20,
    color: Colors.text.primary, textAlign: 'center', marginBottom: 16,
  },
  modalClose: {
    position: 'absolute', top: 14, right: 14,
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: Colors.surface.alt,
    alignItems: 'center', justifyContent: 'center',
  },
  plansRow: { flexDirection: 'row', gap: 10 },
  planCard: {
    flex: 1, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 14,
    padding: 14, borderWidth: 1, borderColor: Colors.surface.alt,
  },
  planCardPro: {
    backgroundColor: 'rgba(80,200,120,0.20)', borderColor: 'rgba(80,200,120,0.20)',
  },
  planName: {
    fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary,
  },
  planPrice: {
    fontFamily: 'JetBrainsMono_700Bold', fontSize: 28,
    color: Colors.text.primary, marginTop: 4,
  },
  planPeriod: {
    fontFamily: 'DMSans_400Regular', fontSize: 12,
    color: Colors.text.tertiary, marginBottom: 10,
  },
  planFeature: {
    fontFamily: 'DMSans_400Regular', fontSize: 11,
    color: Colors.text.secondary, paddingVertical: 2,
  },
  popularTag: {
    position: 'absolute', top: -10, right: 12,
    backgroundColor: 'rgba(212,168,67,0.30)', paddingHorizontal: 8,
    paddingVertical: 2, borderRadius: 8,
  },
  popularTagText: {
    fontFamily: 'DMSans_700Bold', fontSize: 9, color: '#FFF',
    letterSpacing: 0.5,
  },
  freeBtn: {
    marginTop: 12, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1, borderColor: Colors.surface.alt, alignItems: 'center',
  },
  freeBtnText: {
    fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.secondary,
  },
  proBtn: {
    marginTop: 12, paddingVertical: 10, borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.08)', alignItems: 'center',
  },
  proBtnText: {
    fontFamily: 'DMSans_700Bold', fontSize: 12, color: 'rgba(80,200,120,0.20)',
  },

  // Sign out
  reportBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 14, marginTop: Spacing.md,
    borderRadius: 12, borderWidth: 1, borderColor: Colors.primary.default + '20',
    backgroundColor: 'rgba(80,200,120,0.20)' + '08',
  },
  reportText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.accent.green,
  },
  signOutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 14, marginTop: Spacing.md,
    borderRadius: 12, borderWidth: 1, borderColor: 'rgba(240,123,123,0.12)',
    backgroundColor: 'rgba(240,123,123,0.06)',
  },
  signOutText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#F07B7B',
  },
});
