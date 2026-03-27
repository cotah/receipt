import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, Image, StyleSheet, Alert, ScrollView, Pressable } from 'react-native';
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
import api from '../../services/api';

export default function ScanScreen() {
  const router = useRouter();
  const cameraRef = useRef<CameraView>(null);
  const isMounted = useRef(true);
  const [permission, requestPermission] = useCameraPermissions();

  // Multi-photo state
  const [photos, setPhotos] = useState<string[]>([]);
  const [showCamera, setShowCamera] = useState(true);
  const [flashOn, setFlashOn] = useState(false);
  const { isProcessing, processingStatus } = useReceipts();

  // Progress
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
        return prev + 3;
      });
    }, 200);
  }, []);

  const stopFakeProgress = useCallback((final: number) => {
    if (fakeIntervalRef.current) clearInterval(fakeIntervalRef.current);
    setFakeProgress(final);
  }, []);

  // Capture photo and add to array
  const handleCapture = async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
      if (!isMounted.current) return;
      if (photo) {
        const compressed = await compressImage(photo.uri);
        if (!isMounted.current) return;
        setPhotos((prev) => [...prev, compressed]);
        setShowCamera(false); // Show preview after first photo
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '';
      if (msg.includes('unmounted') || msg.includes('Unmounted')) return;
      console.error('Camera capture error:', msg);
    }
  };

  // Pick from gallery (supports multi-select)
  const handlePickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
      allowsMultipleSelection: true,
      selectionLimit: 5 - photos.length,
    });
    if (!result.canceled && result.assets.length > 0) {
      const uris: string[] = [];
      for (const asset of result.assets) {
        const compressed = await compressImage(asset.uri);
        uris.push(compressed);
      }
      setPhotos((prev) => [...prev, ...uris].slice(0, 5));
      setShowCamera(false);
    }
  };

  // Remove a photo
  const removePhoto = (index: number) => {
    setPhotos((prev) => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) setShowCamera(true);
      return next;
    });
  };

  // Go back to camera to add more photos
  const handleAddMore = () => {
    if (photos.length >= 5) {
      Alert.alert('Maximum reached', 'You can add up to 5 photos per receipt.');
      return;
    }
    setShowCamera(true);
  };

  // Reset everything
  const handleRetake = () => {
    setPhotos([]);
    setShowCamera(true);
    stopFakeProgress(0);
  };

  // Process all photos
  const handleProcess = async () => {
    if (photos.length === 0) return;

    startFakeProgress();

    try {
      let receiptId: string;

      if (photos.length === 1) {
        // Single photo — use original endpoint
        const formData = new FormData();
        formData.append('file', {
          uri: photos[0],
          name: 'receipt.jpg',
          type: 'image/jpeg',
        } as any);
        formData.append('source', 'photo');
        const { data } = await api.post('/receipts/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        receiptId = data.receipt_id;
      } else {
        // Multi-photo — use new endpoint
        const formData = new FormData();
        photos.forEach((uri, i) => {
          formData.append('files', {
            uri,
            name: `receipt_part${i + 1}.jpg`,
            type: 'image/jpeg',
          } as any);
        });
        formData.append('source', 'photo');
        const { data } = await api.post('/receipts/upload-multi', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        receiptId = data.receipt_id;
      }

      if (!isMounted.current) return;
      stopFakeProgress(50);

      // Poll for completion
      const startedAt = Date.now();
      const TIMEOUT = 90000;

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
              const { data } = await api.get(`/receipts/${receiptId}/status`);

              if (data.status === 'done') {
                stopFakeProgress(100);
                setTimeout(() => {
                  if (!isMounted.current) return;
                  setPhotos([]);
                  setShowCamera(true);
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

  const displayStatus = isProcessing || fakeProgress > 0
    ? {
        progress: fakeProgress,
        message: fakeProgress < 30
          ? `Uploading ${photos.length} photo${photos.length > 1 ? 's' : ''}...`
          : fakeProgress >= 100
          ? 'Done!'
          : photos.length > 1
          ? `Reading ${photos.length} sections of your receipt...`
          : 'Processing receipt...',
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

  // Preview mode — show captured photos
  if (photos.length > 0 && !showCamera) {
    return (
      <View style={styles.container}>
        {/* Photo strip at top */}
        <View style={styles.photoStripContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.photoStrip}
          >
            {photos.map((uri, i) => (
              <View key={i} style={styles.thumbContainer}>
                <Image source={{ uri }} style={styles.thumb} />
                <Text style={styles.thumbLabel}>Part {i + 1}</Text>
                <Pressable style={styles.thumbRemove} onPress={() => removePhoto(i)}>
                  <Text style={styles.thumbRemoveText}>✕</Text>
                </Pressable>
              </View>
            ))}
          </ScrollView>
        </View>

        {/* Main preview — show last photo */}
        <Image source={{ uri: photos[photos.length - 1] }} style={styles.preview} />

        {/* Hint for long receipts */}
        {photos.length === 1 && (
          <View style={styles.hintBar}>
            <Text style={styles.hintText}>
              📏 Long receipt? Tap "Add more" to capture the rest
            </Text>
          </View>
        )}
        {photos.length > 1 && (
          <View style={styles.hintBar}>
            <Text style={styles.hintText}>
              ✅ {photos.length} parts captured — we'll combine them automatically
            </Text>
          </View>
        )}

        {/* Actions */}
        <View style={styles.previewActions}>
          <Button title="Retake" onPress={handleRetake} variant="secondary" />
          {photos.length < 5 && (
            <Button
              title={`Add more`}
              onPress={handleAddMore}
              variant="secondary"
            />
          )}
          <Button
            title={photos.length > 1 ? `Process (${photos.length})` : 'Process'}
            onPress={handleProcess}
            icon="check"
          />
        </View>

        <ProcessingModal
          visible={fakeProgress > 0}
          status={displayStatus}
          onCancel={() => { handleRetake(); }}
        />
      </View>
    );
  }

  // Camera mode
  return (
    <View style={styles.container}>
      {/* Show photo count if adding more */}
      {photos.length > 0 && (
        <View style={styles.addMoreBanner}>
          <Text style={styles.addMoreText}>
            📸 Adding part {photos.length + 1} — capture the next section
          </Text>
        </View>
      )}

      <CameraView ref={cameraRef} style={styles.camera} facing="back" enableTorch={flashOn}>
        <ReceiptScanner
          onCapture={handleCapture}
          onPickFromGallery={handlePickFromGallery}
          flashOn={flashOn}
          onToggleFlash={() => setFlashOn((v) => !v)}
        />
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
  previewActions: { flexDirection: 'row', justifyContent: 'center', gap: Spacing.sm, padding: Spacing.md, backgroundColor: '#000' },

  // Photo strip
  photoStripContainer: { backgroundColor: '#111', paddingVertical: Spacing.sm, borderBottomWidth: 1, borderBottomColor: '#333' },
  photoStrip: { paddingHorizontal: Spacing.md, gap: Spacing.sm },
  thumbContainer: { position: 'relative', alignItems: 'center' },
  thumb: { width: 56, height: 76, borderRadius: 6, borderWidth: 2, borderColor: Colors.primary.default },
  thumbLabel: { fontFamily: 'DMSans_500Medium', fontSize: 10, color: '#aaa', marginTop: 2 },
  thumbRemove: {
    position: 'absolute', top: -6, right: -6,
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: '#ff4444', alignItems: 'center', justifyContent: 'center',
  },
  thumbRemoveText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  // Hint bar
  hintBar: { backgroundColor: '#1a2a1a', paddingVertical: Spacing.sm, paddingHorizontal: Spacing.md },
  hintText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: '#7ec87e', textAlign: 'center' },

  // Add more banner (on camera)
  addMoreBanner: { backgroundColor: Colors.primary.default, paddingVertical: Spacing.sm, paddingHorizontal: Spacing.md },
  addMoreText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: '#fff', textAlign: 'center' },
});
