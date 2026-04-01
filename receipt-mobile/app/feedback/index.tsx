import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Alert, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import api from '../../services/api';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';

const CATEGORIES = [
  { key: 'bug', label: 'Bug', icon: 'alert-circle' },
  { key: 'suggestion', label: 'Suggestion', icon: 'lightbulb' },
  { key: 'other', label: 'Other', icon: 'message-circle' },
] as const;

export default function FeedbackScreen() {
  const router = useRouter();
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState<string>('bug');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    if (message.trim().length < 5) {
      Alert.alert('Too short', 'Please describe the issue in a bit more detail.');
      return;
    }
    setSending(true);
    try {
      await api.post('/feedback', { message: message.trim(), category });
      setSent(true);
    } catch {
      Alert.alert('Error', 'Could not send your report. Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.successContainer}>
          <View style={styles.successIcon}>
            <Feather name="check-circle" size={48} color={Colors.accent.green} />
          </View>
          <Text style={styles.successTitle}>Sent, thank you!</Text>
          <Text style={styles.successText}>
            We'll review your report and get back to you within 48 hours.
            Thank you for helping the community improve!
          </Text>
          <Pressable style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backBtnText}>Back to Profile</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backArrow}>
            <Feather name="arrow-left" size={22} color={Colors.text.primary} />
          </Pressable>
          <Text style={styles.title}>Report an Issue</Text>
          <View style={{ width: 22 }} />
        </View>

        <View style={styles.content}>
          <Text style={styles.label}>Category</Text>
          <View style={styles.categoryRow}>
            {CATEGORIES.map((cat) => (
              <Pressable
                key={cat.key}
                style={[styles.categoryChip, category === cat.key && styles.categoryChipActive]}
                onPress={() => setCategory(cat.key)}
              >
                <Feather
                  name={cat.icon as any}
                  size={14}
                  color={category === cat.key ? '#FFFFFF' : Colors.text.secondary}
                />
                <Text style={[styles.categoryText, category === cat.key && styles.categoryTextActive]}>
                  {cat.label}
                </Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.label}>Describe the issue</Text>
          <TextInput
            style={styles.textInput}
            placeholder="Tell us what happened..."
            placeholderTextColor={Colors.text.tertiary}
            multiline
            numberOfLines={6}
            textAlignVertical="top"
            value={message}
            onChangeText={setMessage}
            maxLength={2000}
          />
          <Text style={styles.charCount}>{message.length}/2000</Text>

          <Pressable
            style={[styles.sendBtn, (sending || message.trim().length < 5) && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={sending || message.trim().length < 5}
          >
            <Feather name="send" size={16} color="#fff" />
            <Text style={styles.sendBtnText}>{sending ? 'Sending...' : 'Send Report'}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: 14,
  },
  backArrow: { padding: 4 },
  title: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary },
  content: { flex: 1, paddingHorizontal: Spacing.md, paddingTop: 8 },
  label: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.secondary,
    marginBottom: 8, marginTop: 16,
  },
  categoryRow: { flexDirection: 'row', gap: 8 },
  categoryChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
  },
  categoryChipActive: {
    backgroundColor: 'rgba(80,200,120,0.20)', borderColor: Colors.primary.default,
  },
  categoryText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.secondary },
  categoryTextActive: { color: '#FFFFFF' },
  textInput: {
    backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
    padding: 14, fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.primary,
    minHeight: 150, lineHeight: 22,
  },
  charCount: {
    fontFamily: 'DMSans_400Regular', fontSize: 11, color: Colors.text.tertiary,
    textAlign: 'right', marginTop: 4,
  },
  sendBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: 'rgba(80,200,120,0.20)', borderRadius: 12,
    paddingVertical: 14, marginTop: 24,
  },
  sendBtnDisabled: { opacity: 0.5 },
  sendBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#FFFFFF' },
  successContainer: {
    flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32,
  },
  successIcon: { marginBottom: 16 },
  successTitle: {
    fontFamily: 'DMSans_700Bold', fontSize: 22, color: Colors.accent.green, marginBottom: 12,
  },
  successText: {
    fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.secondary,
    textAlign: 'center', lineHeight: 22,
  },
  backBtn: {
    marginTop: 24, paddingVertical: 12, paddingHorizontal: 32,
    borderRadius: 10, backgroundColor: 'rgba(80,200,120,0.20)',
  },
  backBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#FFFFFF' },
});
