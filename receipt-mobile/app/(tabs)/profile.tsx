import React, { useState } from 'react';
import { View, Text, StyleSheet, Alert, Switch, Pressable, Image, TextInput, ScrollView, Share } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { decode } from 'base64-arraybuffer';
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

export default function ProfileScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const signOut = useAuthStore((s) => s.signOut);
  const setProfile = useAuthStore((s) => s.setProfile);

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
    if (!error) {
      setProfile({ ...profile, ...updates } as typeof profile);
    }
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
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.7,
    });

    if (result.canceled || !result.assets[0]) return;

    setUploading(true);
    try {
      const asset = result.assets[0];
      const ext = asset.uri.split('.').pop() ?? 'jpg';
      const path = `${profile!.id}/avatar.${ext}`;

      const base64 = await FileSystem.readAsStringAsync(asset.uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(path, decode(base64), {
          contentType: `image/${ext}`,
          upsert: true,
        });

      if (uploadError) throw uploadError;

      const { data } = supabase.storage.from('avatars').getPublicUrl(path);
      const avatar_url = `${data.publicUrl}?t=${Date.now()}`;
      await updateProfile({ avatar_url });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      Alert.alert('Upload failed', msg);
    } finally {
      setUploading(false);
    }
  };

  const handleReferFriend = async () => {
    try {
      await Share.share({
        message: 'Track your grocery spending with SmartDocket! Download now: https://smartdocket.app/invite',
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
          await signOut();
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  const initials = getInitials(profile?.full_name);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
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
          <Text style={styles.profileName}>{profile?.full_name || 'User'}</Text>
          <Text style={styles.profileEmail}>{profile?.email || ''}</Text>
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
                  <Feather name="user" size={16} color={Colors.primary.default} />
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
                    <Feather name="check" size={16} color={Colors.primary.default} />
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
                  <Feather name="mail" size={16} color={Colors.primary.default} />
                </View>
                <Text style={styles.rowLabel}>Email</Text>
              </View>
              <Text style={styles.rowValueMuted}>{profile?.email || ''}</Text>
            </View>

            <View style={styles.divider} />

            {/* Home Area */}
            <Pressable
              style={styles.row}
              onPress={() => { setAreaText(profile?.home_area ?? ''); setEditingArea(true); }}
            >
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="map-pin" size={16} color={Colors.primary.default} />
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
                    <Feather name="check" size={16} color={Colors.primary.default} />
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
                  <Feather name="bell" size={16} color={Colors.primary.default} />
                </View>
                <Text style={styles.rowLabel}>Notifications</Text>
              </View>
              <Switch
                value={profile?.notify_alerts ?? false}
                onValueChange={handleToggleNotifications}
                trackColor={{ false: Colors.surface.alt, true: Colors.primary.light }}
                thumbColor={profile?.notify_alerts ? Colors.primary.default : '#ccc'}
              />
            </View>

            <View style={styles.divider} />

            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="bar-chart-2" size={16} color={Colors.primary.default} />
                </View>
                <Text style={styles.rowLabel}>Monthly Reports</Text>
              </View>
              <Switch
                value={profile?.notify_reports ?? false}
                onValueChange={handleToggleReports}
                trackColor={{ false: Colors.surface.alt, true: Colors.primary.light }}
                thumbColor={profile?.notify_reports ? Colors.primary.default : '#ccc'}
              />
            </View>
          </Card>
        </View>

        {/* Rewards section */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>REWARDS</Text>
          <Card variant="elevated" style={styles.sectionCard}>
            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="star" size={16} color={Colors.accent.amber} />
                </View>
                <Text style={styles.rowLabel}>Points</Text>
              </View>
              <Text style={styles.rowValueBold}>0</Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.row}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="award" size={16} color={Colors.accent.amber} />
                </View>
                <Text style={styles.rowLabel}>Level</Text>
              </View>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>Starter</Text>
              </View>
            </View>

            <View style={styles.divider} />

            <Pressable style={styles.row} onPress={handleReferFriend}>
              <View style={styles.rowLeft}>
                <View style={styles.iconCircle}>
                  <Feather name="gift" size={16} color={Colors.primary.default} />
                </View>
                <Text style={styles.rowLabel}>Refer a Friend</Text>
              </View>
              <View style={styles.rowRight}>
                <Text style={styles.rowValueAccent}>Share link</Text>
                <Feather name="chevron-right" size={16} color={Colors.primary.default} />
              </View>
            </Pressable>
          </Card>
        </View>

        {/* Sign out */}
        <Pressable style={styles.signOutBtn} onPress={handleSignOut}>
          <Feather name="log-out" size={18} color="#DC3545" />
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
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
    backgroundColor: Colors.primary.default,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 3, borderColor: Colors.primary.light,
  },
  avatarInitials: {
    fontFamily: 'DMSans_700Bold', fontSize: 36, color: '#FFF',
  },
  editBadge: {
    position: 'absolute', bottom: 2, right: 2,
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: Colors.primary.default,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: '#FFF',
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
    backgroundColor: Colors.primary.pale,
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
    color: Colors.primary.default,
  },
  divider: { height: 1, backgroundColor: Colors.surface.alt, marginHorizontal: Spacing.md },

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

  // Sign out
  signOutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 14, marginTop: Spacing.md,
    borderRadius: 12, borderWidth: 1, borderColor: '#DC354520',
    backgroundColor: '#DC354508',
  },
  signOutText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#DC3545',
  },
});
