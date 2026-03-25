import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, Image, StyleSheet, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import ReceiptScanner from '../../components/receipts/ReceiptScanner';
import ProcessingModal from '../../components/receipts/ProcessingModal';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { compressImage } from '../../utils/imageHelpers';
import { useReceipts } from '../../hooks/useReceipts';

export default function ScanScreen() {
  const router = useRouter();
  const cameraRef = useRef<CameraView>(null);
  const isMounted = useRef(true);
  const [permission, requestPermission] = useCameraPermissions();
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const { isProcessing, processingStatus, uploadReceipt, pollProcessingStatus } = useReceipts();

  // Track fake progress for smooth animation
  const [fakeProgress, setFakeProgress] = useState(0);
  const fakeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      isMounted.current = false;
      if (fakeIntervalRef.current) clearInterval(fakeIntervalRef.current);
    };
  }, []);

  const startFakeProgress = useCallback(() => {
    setFakeProgress(0);
    if (fakeIntervalRef.current) clearInterval(fakeIntervalRef.current);
    fakeIntervalRef.current = setInterval(() => {
      setFakeProgress((prev) => {
        if (prev >= 90) {
          if (fakeIntervalRef.current) clearInterval(fakeIntervalRef.current);
          return 90;
        }
        return prev + 5;
      });
    }, 150);
  }, []);

  const stopFakeProgress = useCallback((final: number) => {
    if (fakeIntervalRef.current) clearInterval(fakeIntervalRef.current);
    setFakeProgress(final);
  }, []);

  const handleCapture = async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
      if (!isMounted.current) return;
      if (photo) {
        const compressed = await compressImage(photo.uri);
        if (!isMounted.current) return;
        setCapturedUri(compressed);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '';
      if (msg.includes('unmounted') || msg.includes('Unmounted')) {
        // Camera was unmounted during capture — ignore silently
        return;
      }
      console.error('Camera capture error:', msg);
    }
  };

  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      const compressed = await compressImage(result.assets[0].uri);
      setCapturedUri(compressed);
    }
  };

  const handleProcess = async () => {
    if (!capturedUri) return;

    // Start fake progress animation
    startFakeProgress();

    try {
      const receiptId = await uploadReceipt(capturedUri, 'photo');
      if (!isMounted.current) return;

      // Upload done — jump to 50% and start polling
      stopFakeProgress(50);

      // Poll with progress updates
      const startedAt = Date.now();
      const TIMEOUT = 60000;

      const poll = (): Promise<void> => {
        return new Promise((resolve) => {
          const check = async () => {
            if (!isMounted.current) { resolve(); return; }
            if (Date.now() - startedAt > TIMEOUT) {
              stopFakeProgress(0);
              Alert.alert('Timeout', 'Processing timed out. Please try again.');
              resolve();
              return;
            }

            try {
              const api = (await import('../../services/api')).default;
              const { data } = await api.get(`/receipts/${receiptId}/status`);

              if (data.status === 'done') {
                stopFakeProgress(100);
                setTimeout(() => {
                  if (!isMounted.current) return;
                  setCapturedUri(null);
                  router.push(`/receipt/${receiptId}`);
                }, 300);
                resolve();
                return;
              }

              if (data.status === 'failed') {
                stopFakeProgress(0);
                Alert.alert('Processing failed', data.message || 'Could not process this receipt.');
                resolve();
                return;
              }

              // Still processing — animate between 50-90%
              const elapsed = (Date.now() - startedAt) / TIMEOUT;
              setFakeProgress(Math.min(50 + Math.floor(elapsed * 40), 90));
              setTimeout(check, 2000);
            } catch {
              stopFakeProgress(0);
              resolve();
            }
          };
          check();
        });
      };

      await poll();
    } catch (e: unknown) {
      stopFakeProgress(0);
      const msg = e instanceof Error ? e.message : 'Upload failed';
      Alert.alert('Error', msg);
    }
  };

  // Merge fake progress with server progress for the modal
  const displayStatus = isProcessing || fakeProgress > 0
    ? {
        progress: fakeProgress,
        message: fakeProgress < 50 ? 'Uploading...' : fakeProgress >= 100 ? 'Done!' : 'Processing receipt...',
      }
    : processingStatus;

  if (!permission) return <View style={styles.container} />;

  if (!permission.granted) {
    return (
      <View style={[styles.container, styles.center]}>
        <Text style={styles.permText}>Camera permission is required to scan receipts</Text>
        <Button title="Grant Permission" onPress={requestPermission} />
      </View>
    );
  }

  // Preview captured image
  if (capturedUri) {
    return (
      <View style={styles.container}>
        <Image source={{ uri: capturedUri }} style={styles.preview} />
        <View style={styles.previewActions}>
          <Button title="Retake" onPress={() => { setCapturedUri(null); stopFakeProgress(0); }} variant="secondary" />
          <Button title="Process Receipt" onPress={handleProcess} icon="check" />
        </View>
        <ProcessingModal
          visible={fakeProgress > 0}
          status={displayStatus}
          onCancel={() => { setCapturedUri(null); stopFakeProgress(0); }}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back">
        <ReceiptScanner onCapture={handleCapture} onPickFromGallery={handlePickFromGallery} />
      </CameraView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  center: { alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surface.background },
  camera: { flex: 1 },
  permText: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: Colors.text.primary, textAlign: 'center', marginBottom: Spacing.md, paddingHorizontal: Spacing.lg },
  preview: { flex: 1, resizeMode: 'contain' },
  previewActions: { flexDirection: 'row', justifyContent: 'center', gap: Spacing.md, padding: Spacing.lg, backgroundColor: '#000' },
});
