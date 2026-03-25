import React, { useRef, useEffect } from 'react';
import { View, Text, FlatList, StyleSheet, KeyboardAvoidingView, Platform, Keyboard } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { GestureDetector } from 'react-native-gesture-handler';
import { useTabSwipe } from '../../hooks/useTabSwipe';
import ChatBubble from '../../components/chat/ChatBubble';
import ChatInput from '../../components/chat/ChatInput';
import TypingIndicator from '../../components/chat/TypingIndicator';
import ProfileAvatar from '../../components/ui/ProfileAvatar';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useChat } from '../../hooks/useChat';
import { useAuthStore } from '../../stores/authStore';

const SUGGESTIONS = [
  'How much this month?',
  "Where's milk cheapest?",
  'What am I buying most?',
  'Compare last 2 months',
];

export default function ChatScreen() {
  const { messages, isStreaming, sendMessage } = useChat();
  const profile = useAuthStore((s) => s.profile);
  const firstName = profile?.full_name?.split(' ')[0] || 'there';
  const flatListRef = useRef<FlatList>(null);
  const swipe = useTabSwipe(3);

  // Auto-scroll when messages change or streaming
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  // Scroll when keyboard appears
  useEffect(() => {
    const sub = Keyboard.addListener('keyboardDidShow', () => {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 150);
    });
    return () => sub.remove();
  }, []);

  return (
    <GestureDetector gesture={swipe}>
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.flex}
      keyboardVerticalOffset={0}
    >
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>SmartDocket AI</Text>
            <Text style={styles.subtitle}>Ask about your spending</Text>
          </View>
          <ProfileAvatar size={32} />
        </View>

        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ChatBubble content={item.content} role={item.role} timestamp={item.created_at} />
          )}
          contentContainerStyle={styles.messagesList}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() => {
            flatListRef.current?.scrollToEnd({ animated: true });
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>{`Hello, ${firstName}! 👋`}</Text>
              <Text style={styles.emptyText}>How can I help you today? Ask me anything about your grocery spending.</Text>
            </View>
          }
          ListFooterComponent={isStreaming ? <TypingIndicator /> : null}
        />
        <ChatInput
          onSend={sendMessage}
          isStreaming={isStreaming}
          suggestions={messages.length === 0 ? SUGGESTIONS : undefined}
        />
      </SafeAreaView>
    </KeyboardAvoidingView>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, backgroundColor: Colors.surface.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: Spacing.md, paddingTop: Spacing.md, paddingBottom: Spacing.sm, borderBottomWidth: 1, borderBottomColor: Colors.surface.alt },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },
  subtitle: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary },
  messagesList: { paddingVertical: Spacing.md, flexGrow: 1 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xxl, marginTop: 80 },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', lineHeight: 22 },
});
