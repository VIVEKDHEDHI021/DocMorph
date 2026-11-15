/**
 * Native Android & Platform Services for DocMorph.
 *
 * Provides native file picking via SAF, file saving via Filesystem,
 * opening PDFs via FileOpener intent, sharing via Share Sheet,
 * hardware back-button handling, and platform detection.
 */

import { Capacitor } from '@capacitor/core';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';
import { FileOpener } from '@capacitor-community/file-opener';
import { FilePicker } from '@capawesome/capacitor-file-picker';
import { App as CapApp } from '@capacitor/app';
import { StatusBar, Style } from '@capacitor/status-bar';

export interface PickedPdfResult {
  file?: File;
  name: string;
  size: number;
  mimeType: string;
  blob?: Blob;
  path?: string;
  uri?: string;
  base64Data?: string;
}

export class NativeService {
  /**
   * Returns true if running as an installed native app on Android.
   */
  static isNative(): boolean {
    return Capacitor.isNativePlatform();
  }

  /**
   * Initializes platform-specific UI (Status bar, back button).
   */
  static async initializeAppUI(onBackButton?: () => boolean): Promise<void> {
    if (!this.isNative()) return;

    try {
      await StatusBar.setStyle({ style: Style.Dark });
      await StatusBar.setBackgroundColor({ color: '#ffffff' });
    } catch (e) {
      console.warn('Status bar styling unavailable:', e);
    }

    try {
      CapApp.addListener('backButton', ({ canGoBack }) => {
        if (onBackButton) {
          const handled = onBackButton();
          if (handled) return;
        }

        if (canGoBack) {
          window.history.back();
        } else {
          CapApp.exitApp();
        }
      });
    } catch (e) {
      console.warn('Hardware back button listener unavailable:', e);
    }
  }

  /**
   * Opens native Android Storage Access Framework document picker or web fallback.
   */
  static async pickPdfFile(): Promise<PickedPdfResult | null> {
    if (this.isNative()) {
      try {
        const result = await FilePicker.pickFiles({
          types: ['application/pdf'],
          limit: 1,
          readData: true,
        });

        if (!result.files || result.files.length === 0) {
          return null; // User cancelled
        }

        const picked = result.files[0];
        const name = picked.name || 'document.pdf';
        const size = picked.size || 0;
        const mimeType = picked.mimeType || 'application/pdf';

        if (!mimeType.includes('pdf') && !name.toLowerCase().endsWith('.pdf')) {
          throw new Error('Please select a valid PDF document.');
        }

        // Convert base64 data to Blob/File for upload
        let blob: Blob;
        if (picked.data) {
          const byteCharacters = atob(picked.data);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          blob = new Blob([byteArray], { type: 'application/pdf' });
        } else {
          throw new Error('Unable to read selected document data.');
        }

        const file = new File([blob], name, { type: 'application/pdf' });

        return {
          file,
          blob,
          name,
          size: size || blob.size,
          mimeType: 'application/pdf',
          path: picked.path,
          uri: picked.path,
          base64Data: picked.data,
        };
      } catch (err: any) {
        if (err.message && err.message.toLowerCase().includes('cancel')) {
          return null;
        }
        console.error('Native file picker error:', err);
        throw err;
      }
    }

    // Web Fallback: programmatic input creation
    return new Promise((resolve, reject) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'application/pdf';
      input.style.display = 'none';

      input.onchange = () => {
        const file = input.files?.[0];
        if (file) {
          if (!file.name.toLowerCase().endsWith('.pdf')) {
            reject(new Error('Selected file is not a PDF.'));
            return;
          }
          resolve({
            file,
            blob: file,
            name: file.name,
            size: file.size,
            mimeType: file.type || 'application/pdf',
          });
        } else {
          resolve(null);
        }
        document.body.removeChild(input);
      };

      input.oncancel = () => {
        resolve(null);
        document.body.removeChild(input);
      };

      document.body.appendChild(input);
      input.click();
    });
  }

  /**
   * Saves PDF blob bytes to device storage and returns local URI.
   */
  static async savePdfLocally(blob: Blob, filename: string): Promise<string> {
    if (!this.isNative()) {
      // Browser download fallback
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return url;
    }

    // Convert Blob to Base64
    const base64Data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const res = reader.result as string;
        // Strip data:application/pdf;base64,
        const base64 = res.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

    const sanitizedFilename = filename.replace(/[^\w\-. ]/g, '_');

    // Save to Cache / Documents directory
    const saved = await Filesystem.writeFile({
      path: sanitizedFilename,
      data: base64Data,
      directory: Directory.Cache,
    });

    return saved.uri;
  }

  /**
   * Opens a PDF file using Android's system document viewer intent.
   */
  static async openPdf(fileUri: string): Promise<void> {
    if (this.isNative()) {
      try {
        await FileOpener.open({
          filePath: fileUri,
          contentType: 'application/pdf',
          openWithDefault: false,
        });
        return;
      } catch (e: any) {
        console.error('FileOpener error:', e);
        throw new Error('No PDF viewer application found on device. You can share or download the file.');
      }
    }

    // Web fallback: open in new tab
    window.open(fileUri, '_blank');
  }

  /**
   * Shares a PDF using Android's native share sheet.
   */
  static async sharePdf(fileUri: string, filename: string): Promise<void> {
    if (this.isNative()) {
      try {
        await Share.share({
          title: `Share ${filename}`,
          text: `Personalized academic document: ${filename}`,
          url: fileUri,
          dialogTitle: 'Share Personalized PDF',
        });
        return;
      } catch (e: any) {
        if (e.message && e.message.toLowerCase().includes('cancel')) {
          return;
        }
        console.error('Native Share error:', e);
        throw e;
      }
    }

    if (navigator.share) {
      try {
        await navigator.share({
          title: filename,
          text: `DocMorph Personalized PDF: ${filename}`,
          url: window.location.href,
        });
      } catch (e) {
        console.warn('Web share cancelled or unavailable:', e);
      }
    } else {
      alert('Sharing is not supported directly in this web browser. Please download the file.');
    }
  }
}
