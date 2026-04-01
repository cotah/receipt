import React, { useState } from 'react';
import { View, Text, StyleSheet, Alert, Switch, Pressable, Image, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { decode } from 'base64-arraybuffer';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import { supabase } from '../../services/supabase';

export default function SettingsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const signOut = useAuthStore((s) => s.signOut);
  const setProfile = useAuthStore((s) => s.setProfile);

  const [editingArea, setEditingArea] = useState(false);
  const [areaText, setAreaText] = useState(profile?.home_area ?? '');
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
          <Pressable onPress={handlePickAvatar} style={styles.avatarWrap}>
            {profile?.avatar_url ? (
              <Image source={{ uri: profile.avatar_url }} style={styles.avatarImg} />
            ) : (
              <View style={styles.avatar}>
                <Feather name="user" size={32} color={Colors.primary.default} />
              </View>
            )}
            <View style={styles.cameraBadge}>
              <Feather name="camera" size={12} color="#FFF" />
            </View>
          </Pressable>
          {uploading && <Text style={styles.uploadingText}>Uploading...</Text>}
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
            <Switch
              value={profile?.notify_alerts ?? false}
              onValueChange={handleToggleNotifications}
              trackColor={{ false: Colors.surface.alt, true: Colors.primary.light }}
              thumbColor={profile?.notify_alerts ? Colors.primary.default : '#ccc'}
            />
          </Card>

          <Card style={styles.row}>
            <View style={styles.rowLeft}>
              <Feather name="mail" size={18} color={Colors.text.secondary} />
              <Text style={styles.rowLabel}>Monthly Reports</Text>
            </View>
            <Switch
              value={profile?.notify_reports ?? false}
              onValueChange={handleToggleReports}
              trackColor={{ false: Colors.surface.alt, true: Colors.primary.light }}
              thumbColor={profile?.notify_reports ? Colors.primary.default : '#ccc'}
            />
          </Card>

          <Card style={styles.row}>
            <View style={styles.rowLeft}>
              <Feather name="map-pin" size={18} color={Colors.text.secondary} />
              <Text style={styles.rowLabel}>Home Area</Text>
            </View>
            {editingArea ? (
              <View style={styles.areaInput}>
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
                  <Feather name="check" size={18} color={Colors.primary.default} />
                </Pressable>
              </View>
            ) : (
              <Pressable onPress={() => { setAreaText(profile?.home_area ?? ''); setEditingArea(true); }}>
                <Text style={styles.rowValue}>{profile?.home_area || 'Not set'}</Text>
              </Pressable>
            )}
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
    color: '#FFFFFF',
  },
  content: { flex: 1, paddingHorizontal: Spacing.md },
  profileCard: {
    alignItems: 'center',
    paddingVertical: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  avatarWrap: { position: 'relative', marginBottom: Spacing.sm },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primary.pale,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarImg: {
    width: 64,
    height: 64,
    borderRadius: 32,
  },
  cameraBadge: {
    position: 'absolute',
    bottom: 0,
    right: -2,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primary.default,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FFF',
  },
  uploadingText: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 12,
    color: Colors.text.tertiary,
    marginBottom: 4,
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
  areaInput: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  textInput: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    color: Colors.text.primary,
    borderBottomWidth: 1,
    borderBottomColor: Colors.primary.default,
    minWidth: 100,
    paddingVertical: 2,
  },
  signOutSection: { marginTop: 'auto', paddingBottom: Spacing.xl },
});
