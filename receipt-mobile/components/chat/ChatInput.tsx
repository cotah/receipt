import React, { useState } from 'react';
import { View, TextInput, Pressable, ScrollView, Text, StyleSheet } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';

interface ChatInputProps {
  onSend: (text: string) => void;
  isStreaming: boolean;
  suggestions?: string[];
}

export default function ChatInput({ onSend, isStreaming, suggestions }: ChatInputProps) {
  const [text, setText] = useState('');

  const handleSend = () => {
    if (!text.trim() || isStreaming) return;
    onSend(text.trim());
    setText('');
  };

  return (
    <View style={styles.container}>
      {suggestions && suggestions.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips} contentContainerStyle={{ gap: Spacing.sm }}>
          {suggestions.map((s) => (
            <Pressable key={s} onPress={() => onSend(s)} style={styles.chip}>
              <Text style={styles.chipText}>{s}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="Ask about your spending..."
          placeholderTextColor={Colors.text.tertiary}
          multiline
          maxLength={500}
          onSubmitEditing={handleSend}
        />
        <Pressable
          onPress={handleSend}
          disabled={!text.trim() || isStreaming}
          style={[styles.sendBtn, (!text.trim() || isStreaming) && styles.sendBtnDisabled]}
        >
          <Feather name="arrow-up" size={20} color="#FFF" />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderTopWidth: 0.5,
    borderTopColor: 'rgba(255,255,255,0.08)',
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  chips: { paddingHorizontal: Spacing.md, paddingTop: Spacing.sm },
  chip: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: BorderRadius.full,
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.10)',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  chipText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.accent.green },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: Spacing.sm,
    paddingHorizontal: Spacing.md,
  },
  input: {
    flex: 1,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
    color: '#FFFFFF',
    maxHeight: 100,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: BorderRadius.md,
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.10)',
    marginRight: Spacing.sm,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(80,200,120,0.25)',
    borderWidth: 0.5,
    borderColor: 'rgba(80,200,120,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.3 },
});
