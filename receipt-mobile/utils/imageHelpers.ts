import * as ImageManipulator from 'expo-image-manipulator';
import * as FileSystem from 'expo-file-system/legacy';

export async function compressImage(uri: string): Promise<string> {
  const info = await FileSystem.getInfoAsync(uri);
  const maxBytes = 2 * 1024 * 1024; // 2MB

  if (info.exists && info.size && info.size <= maxBytes) {
    return uri;
  }

  const result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: 1600 } }],
    { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG }
  );
  return result.uri;
}

export async function getImageBase64(uri: string): Promise<string> {
  return await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
}
