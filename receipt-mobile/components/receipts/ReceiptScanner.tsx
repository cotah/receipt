import React from 'react';
import { View, Text, Pressable, StyleSheet, Dimensions } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';

const { width, height } = Dimensions.get('window');
const FRAME_W = width * 0.8;
const FRAME_H = height * 0.5;
const CORNER_SIZE = 30;

interface ReceiptScannerProps {
  onCapture: () => void;
  onPickFromGallery: () => void;
  flashOn?: boolean;
  onToggleFlash?: () => void;
}

function Corner({ style }: { style: object }) {
  return <View style={[styles.corner, style]} />;
}

export default function ReceiptScanner({ onCapture, onPickFromGallery, flashOn, onToggleFlash }: ReceiptScannerProps) {
  return (
    <View style={styles.overlay}>
      {/* Guide frame */}
      <View style={styles.frame}>
        <Corner style={styles.topLeft} />
        <Corner style={styles.topRight} />
        <Corner style={styles.bottomLeft} />
        <Corner style={styles.bottomRight} />
      </View>

      <Text style={styles.hint}>Align receipt within the frame</Text>

      {/* Bottom controls */}
      <View style={styles.controls}>
        <Pressable onPress={onPickFromGallery} style={styles.sideBtn}>
          <Feather name="image" size={24} color="#FFF" />
        </Pressable>
        <Pressable onPress={onCapture} style={styles.captureBtn}>
          <View style={styles.captureBtnInner} />
        </Pressable>
        <Pressable onPress={onToggleFlash} style={styles.sideBtn}>
          <Feather name={flashOn ? 'zap' : 'zap-off'} size={24} color="#FFF" />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  frame: {
    width: FRAME_W,
    height: FRAME_H,
    position: 'relative',
  },
  corner: {
    position: 'absolute',
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderColor: Colors.accent.green,
  },
  topLeft: { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 12 },
  topRight: { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 12 },
  bottomLeft: { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 12 },
  bottomRight: { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 12 },
  hint: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
    color: '#FFF',
    marginTop: Spacing.lg,
    textAlign: 'center',
  },
  controls: {
    position: 'absolute',
    bottom: 60,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    paddingHorizontal: Spacing.xxl,
  },
  sideBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  captureBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#FFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: Spacing.xl,
  },
  captureBtnInner: {
    width: 62,
    height: 62,
    borderRadius: 31,
    borderWidth: 3,
    borderColor: Colors.primary.dark,
  },
});
