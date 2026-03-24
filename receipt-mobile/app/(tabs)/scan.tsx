import React, { useState, useRef } from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
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
  const [permission, requestPermission] = useCameraPermissions();
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const { isProcessing, processingStatus, uploadReceipt, pollProcessingStatus } = useReceipts();

  const handleCapture = async () => {
    if (!cameraRef.current) return;
    const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
    if (photo) {
      const compressed = await compressImage(photo.uri);
      setCapturedUri(compressed);
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
    const receiptId = await uploadReceipt(capturedUri, 'photo');
    await pollProcessingStatus(receiptId);
    setCapturedUri(null);
    router.push(`/receipt/${receiptId}`);
  };

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
          <Button title="Retake" onPress={() => setCapturedUri(null)} variant="secondary" />
          <Button title="Process Receipt" onPress={handleProcess} icon="check" />
        </View>
        <ProcessingModal
          visible={isProcessing}
          status={processingStatus}
          onCancel={() => setCapturedUri(null)}
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
