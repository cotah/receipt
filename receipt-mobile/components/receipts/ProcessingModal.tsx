import React from 'react';
import { View, Text, Modal, StyleSheet } from 'react-native';
import Button from '../ui/Button';
import { Colors } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface ProcessingModalProps {
  visible: boolean;
  status: { progress: number; message: string } | null;
  onCancel: () => void;
}

export default function ProcessingModal({ visible, status, onCancel }: ProcessingModalProps) {
  const progress = status?.progress ?? 0;
  const message = status?.message ?? 'Preparing...';

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.overlay}>
        <View style={styles.modal}>
          <Text style={styles.title}>Processing Receipt</Text>
          <Text style={styles.message}>{message}</Text>

          <View style={styles.progressBg}>
            <View style={[styles.progressFill, { width: `${progress}%` }]} />
          </View>
          <Text style={styles.percent}>{progress}%</Text>

          <Button title="Cancel" onPress={onCancel} variant="ghost" size="sm" />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modal: {
    backgroundColor: 'rgba(26,58,42,0.95)',
    borderRadius: BorderRadius.xl,
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.15)',
    padding: Spacing.lg,
    width: '80%',
    alignItems: 'center',
  },
  title: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: '#FFFFFF', marginBottom: Spacing.sm },
  message: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: 'rgba(255,255,255,0.50)', marginBottom: Spacing.md },
  progressBg: {
    width: '100%',
    height: 8,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: Spacing.sm,
  },
  progressFill: {
    height: '100%',
    backgroundColor: Colors.accent.green,
    borderRadius: 4,
  },
  percent: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.50)', marginBottom: Spacing.md },
});
