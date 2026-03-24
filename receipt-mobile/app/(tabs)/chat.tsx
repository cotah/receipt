import React from 'react';
import { View, Text, FlatList, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import ChatBubble from '../../components/chat/ChatBubble';
import ChatInput from '../../components/chat/ChatInput';
import TypingIndicator from '../../components/chat/TypingIndicator';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useChat } from '../../hooks/useChat';

const SUGGESTIONS = [
  'How much this month?',
  "Where's milk cheapest?",
  'What am I buying most?',
  'Compare last 2 months',
];

export default function ChatScreen() {
  const { messages, isStreaming, sendMessage } = useChat();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Receipt AI</Text>
        <Text style={styles.subtitle}>Ask about your spending</Text>
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.chatArea}
        keyboardVerticalOffset={90}
      >
        <FlatList
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ChatBubble content={item.content} role={item.role} timestamp={item.created_at} />
          )}
          contentContainerStyle={styles.messagesList}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>Start a conversation</Text>
              <Text style={styles.emptyText}>Ask me anything about your grocery spending, prices, or shopping habits.</Text>
            </View>
          }
          ListFooterComponent={isStreaming ? <TypingIndicator /> : null}
        />
        <ChatInput
          onSend={sendMessage}
          isStreaming={isStreaming}
          suggestions={messages.length === 0 ? SUGGESTIONS : undefined}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  header: { paddingHorizontal: Spacing.md, paddingTop: Spacing.md, paddingBottom: Spacing.sm, borderBottomWidth: 1, borderBottomColor: Colors.surface.alt },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },
  subtitle: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary },
  chatArea: { flex: 1 },
  messagesList: { paddingVertical: Spacing.md },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xxl, marginTop: 80 },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', lineHeight: 22 },
});
