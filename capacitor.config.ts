import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.docmorph.app',
  appName: 'DocMorph',
  webDir: 'frontend/dist',
  server: {
    androidScheme: 'https',
    cleartext: true,
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#ffffff',
    },
  },
};

export default config;

