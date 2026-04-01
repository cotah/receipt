import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';

interface ChatBubbleProps {
  content: string;
  role: 'user' | 'assistant';
  timestamp?: string;
}

export default function ChatBubble({ content, role, timestamp }: ChatBubbleProps) {
  const isUser = role === 'user';

  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAssistant]}>
      {!isUser && (
        <View style={styles.avatar}>
          <Feather name="zap" size={14} color="#FFF" />
        </View>
      )}
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        <Text style={[styles.text, isUser ? styles.textUser : styles.textAssistant]}>{content}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginBottom: Spacing.sm, paddingHorizontal: Spacing.md },
  rowUser: { flexDirection: 'row', justifyContent: 'flex-end' },
  rowAssistant: { flexDirection: 'row', justifyContent: 'flex-start' },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(80,200,120,0.20)',
    borderWidth: 0.5,
    borderColor: 'rgba(80,200,120,0.30)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
    marginTop: 4,
  },
  bubble: {
    maxWidth: '78%',
    padding: Spacing.md,
    borderWidth: 0.5,
  },
  bubbleUser: {
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: BorderRadius.lg,
    borderBottomRightRadius: BorderRadius.sm,
  },
  bubbleAssistant: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: BorderRadius.lg,
    borderBottomLeftRadius: BorderRadius.sm,
  },
  text: { fontSize: 15, lineHeight: 22 },
  textUser: { fontFamily: 'DMSans_400Regular', color: '#FFFFFF' },
  textAssistant: { fontFamily: 'DMSans_400Regular', color: '#FFFFFF' },
});
