import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, Image, StyleSheet, Alert, ScrollView, Pressable, Vibration } from 'react-native';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Feather } from '@expo/vector-icons';
import ReceiptScanner from '../../components/receipts/ReceiptScanner';
import ProcessingModal from '../../components/receipts/ProcessingModal';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing, Fonts } from '../../constants/typography';
import { compressImage } from '../../utils/imageHelpers';
import { useReceipts } from '../../hooks/useReceipts';
import api from '../../services/api';

type ScanMode = 'receipt' | 'barcode';

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

  // Scan mode: receipt (default) or barcode
  const [scanMode, setScanMode] = useState<ScanMode>('receipt');
  const barcodeCooldown = useRef(false);

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

  // Reset everything — cancel any in-progress processing
  const handleRetake = async () => {
    // If there's a receipt being processed, delete it
    if (currentReceiptIdRef.current) {
      try {
        await api.delete(`/receipts/${currentReceiptIdRef.current}`);
      } catch {
        // Ignore — might not exist yet or already deleted
      }
      currentReceiptIdRef.current = null;
    }
    setPhotos([]);
    setShowCamera(true);
    stopFakeProgress(0);
  };

  // Track current processing receipt for cancel
  const currentReceiptIdRef = useRef<string | null>(null);

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
      currentReceiptIdRef.current = receiptId;
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
                currentReceiptIdRef.current = null;
                setTimeout(() => {
                  if (!isMounted.current) return;
                  setPhotos([]);
                  setShowCamera(true);
                  // Ask user if they want to scan barcodes for double points
                  Alert.alert(
                    '✅ Receipt processed!',
                    'Scan barcodes of your products now for double points (30 pts each)!',
                    [
                      {
                        text: 'Skip',
                        style: 'cancel',
                        onPress: () => router.push(`/receipt/${receiptId}`),
                      },
                      {
                        text: 'Scan barcodes ⭐',
                        onPress: () => router.push(`/link-barcodes?receiptId=${receiptId}`),
                      },
                    ],
                  );
                }, 300);
                resolve();
                return;
              }

              if (data.status === 'failed') {
                stopFakeProgress(0);
                currentReceiptIdRef.current = null;
                Alert.alert('Processing failed', data.message || 'Could not process this receipt.');
                resolve();
                return;
              }

              // Still processing or saving items — update progress
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

  // Barcode scan handler
  const handleBarcodeScan = useCallback((result: BarcodeScanningResult) => {
    if (barcodeCooldown.current) return;
    barcodeCooldown.current = true;
    Vibration.vibrate(100);
    // Navigate to barcode results page
    router.push(`/barcode-scanner?scanned=${result.data}`);
    // Reset cooldown after navigation
    setTimeout(() => { barcodeCooldown.current = false; }, 3000);
  }, [router]);

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

      {/* Mode toggle — Receipt / Barcode */}
      {photos.length === 0 && (
        <View style={styles.modeToggle}>
          <Pressable
            onPress={() => setScanMode('receipt')}
            style={[styles.modeBtn, scanMode === 'receipt' && styles.modeBtnActive]}
          >
            <Text style={[styles.modeBtnText, scanMode === 'receipt' && styles.modeBtnTextActive]}>
              🧾 Receipt
            </Text>
          </Pressable>
          <Pressable
            onPress={() => setScanMode('barcode')}
            style={[styles.modeBtn, scanMode === 'barcode' && styles.modeBtnActive]}
          >
            <Text style={[styles.modeBtnText, scanMode === 'barcode' && styles.modeBtnTextActive]}>
              ▮▮▮ Barcode
            </Text>
          </Pressable>
        </View>
      )}

      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing="back"
        enableTorch={flashOn}
        barcodeScannerSettings={scanMode === 'barcode' ? { barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] } : undefined}
        onBarcodeScanned={scanMode === 'barcode' ? handleBarcodeScan : undefined}
      >
        {scanMode === 'receipt' ? (
          <ReceiptScanner
            onCapture={handleCapture}
            onPickFromGallery={handlePickFromGallery}
            flashOn={flashOn}
            onToggleFlash={() => setFlashOn((v) => !v)}
          />
        ) : (
          /* Barcode scanning overlay */
          <View style={styles.barcodeOverlay}>
            <View style={styles.barcodeTop} />
            <View style={styles.barcodeMiddle}>
              <View style={styles.barcodeSide} />
              <View style={styles.barcodeViewfinder}>
                <View style={[styles.barcodeCorner, styles.bcTL]} />
                <View style={[styles.barcodeCorner, styles.bcTR]} />
                <View style={[styles.barcodeCorner, styles.bcBL]} />
                <View style={[styles.barcodeCorner, styles.bcBR]} />
                <View style={styles.barcodeLine} />
              </View>
              <View style={styles.barcodeSide} />
            </View>
            <View style={styles.barcodeBottom}>
              <Text style={styles.barcodeHint}>Point at a product barcode</Text>
              <Pressable onPress={() => setFlashOn((v) => !v)} style={styles.barcodeFlash}>
                <Text style={styles.barcodeFlashText}>{flashOn ? '⚡ Flash ON' : '💡 Flash'}</Text>
              </Pressable>
            </View>
          </View>
        )}
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
  thumb: { width: 56, height: 76, borderRadius: 6, borderWidth: 2, borderColor: 'rgba(80,200,120,0.25)' },
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
  addMoreBanner: { backgroundColor: 'rgba(80,200,120,0.20)', paddingVertical: Spacing.sm, paddingHorizontal: Spacing.md },
  addMoreText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: '#fff', textAlign: 'center' },

  // Mode toggle
  modeToggle: {
    position: 'absolute', top: 60, left: 0, right: 0, zIndex: 20,
    flexDirection: 'row', justifyContent: 'center', gap: 4,
    paddingHorizontal: Spacing.xl,
  },
  modeBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 12,
    backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center',
  },
  modeBtnActive: {
    backgroundColor: 'rgba(80,200,120,0.25)',
    borderWidth: 0.5,
    borderColor: 'rgba(80,200,120,0.4)',
  },
  modeBtnText: {
    fontFamily: 'DMSans_600SemiBold', fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
  },
  modeBtnTextActive: {
    color: '#7DDFAA',
  },

  // Barcode overlay
  barcodeOverlay: { ...StyleSheet.absoluteFillObject },
  barcodeTop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  barcodeMiddle: { flexDirection: 'row', height: 160 },
  barcodeSide: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  barcodeViewfinder: {
    width: 300, height: 160, borderRadius: 12, position: 'relative',
    justifyContent: 'center', alignItems: 'center',
  },
  barcodeCorner: {
    position: 'absolute', width: 24, height: 24,
    borderColor: '#3CB371', borderWidth: 3,
  },
  bcTL: { top: 0, left: 0, borderRightWidth: 0, borderBottomWidth: 0, borderTopLeftRadius: 8 },
  bcTR: { top: 0, right: 0, borderLeftWidth: 0, borderBottomWidth: 0, borderTopRightRadius: 8 },
  bcBL: { bottom: 0, left: 0, borderRightWidth: 0, borderTopWidth: 0, borderBottomLeftRadius: 8 },
  bcBR: { bottom: 0, right: 0, borderLeftWidth: 0, borderTopWidth: 0, borderBottomRightRadius: 8 },
  barcodeLine: {
    width: '80%', height: 2, backgroundColor: '#3CB371', opacity: 0.6,
  },
  barcodeBottom: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center', paddingTop: 28, gap: 16,
  },
  barcodeHint: {
    fontFamily: 'DMSans_500Medium', fontSize: 15, color: 'rgba(255,255,255,0.7)',
  },
  barcodeScanBtn: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderWidth: 2, borderColor: 'rgba(80,200,120,0.4)',
    alignItems: 'center', justifyContent: 'center',
  },
  barcodeScanBtnInner: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: 'rgba(80,200,120,0.1)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.3)',
    alignItems: 'center', justifyContent: 'center',
  },
  barcodeFlash: {
    backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 8,
  },
  barcodeFlashText: {
    fontFamily: 'DMSans_500Medium', fontSize: 13, color: 'rgba(255,255,255,0.7)',
  },
});
