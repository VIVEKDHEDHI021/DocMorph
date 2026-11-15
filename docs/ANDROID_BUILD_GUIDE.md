# DOCMORPH — ANDROID BUILD GUIDE

**Product:** DocMorph  
**Target Platform:** Android  
**Framework:** Capacitor 8  
**Package Name:** `com.docmorph.app`  
**Last Updated:** November 2026  

---

## 1. Prerequisites & Toolchain Requirements

To build DocMorph for Android, ensure the following tools are installed on your build machine:

| Component | Minimum Version | Verified Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Node.js** | 18+ LTS | 20+ LTS | JavaScript / TypeScript runtime |
| **npm** | 9+ | 10+ | Package manager |
| **Java Development Kit** | OpenJDK 17 | OpenJDK 17.0.20 | Android Gradle daemon runtime |
| **Android SDK** | API Level 34+ | API Level 34, 35, 36 | Android platform SDKs |
| **Android Build-Tools** | 34.0.0+ | 35.0.0 & 36.0.0 | Compilation and APK packaging |
| **Gradle Wrapper** | 8.11+ | 8.14.3 | Android build automation |

### Environment Variables Verification
Ensure the following variables are configured in your system environment:
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:Path += ";$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\build-tools\35.0.0"
```

---

## 2. Project Build Scripts

The root `package.json` contains unified scripts orchestrating frontend builds and native Gradle tasks:

```json
{
  "scripts": {
    "frontend:dev": "npm --prefix frontend run dev",
    "frontend:build": "npm --prefix frontend run build",
    "cap:sync": "cap sync android",
    "cap:open": "cap open android",
    "cap:run": "cap run android",
    "android:build:debug": "npm run frontend:build && cap sync android && cd android && gradlew.bat assembleDebug",
    "android:build:release": "npm run frontend:build && cap sync android && cd android && gradlew.bat assembleRelease",
    "android:bundle:release": "npm run frontend:build && cap sync android && cd android && gradlew.bat bundleRelease"
  }
}
```

---

## 3. Step-by-Step Build Instructions

### Step 1: Install Dependencies
```powershell
# Root dependencies (Capacitor core, CLI, plugins)
npm install

# Frontend dependencies (React, Vite, PDF.js, Tailwind)
cd frontend
npm install
cd ..
```

### Step 2: Build Production Frontend Assets
Compile the React TypeScript frontend into `frontend/dist/`:
```powershell
npm run frontend:build
```

### Step 3: Synchronize Web Assets with Android Platform
Copy compiled web assets and update native plugin bindings:
```powershell
npx cap sync android
```

### Step 4: Build Debug APK (For local development and testing)
```powershell
npm run android:build:debug
```
**Output Location:**
`android/app/build/outputs/apk/debug/app-debug.apk`

### Step 5: Build Signed Release APK (For direct device installation)
```powershell
npm run android:build:release
```
**Output Location:**
`android/app/build/outputs/apk/release/app-release.apk`

### Step 6: Build Signed Release Android App Bundle (For Google Play Console)
```powershell
npm run android:bundle:release
```
**Output Location:**
`android/app/build/outputs/bundle/release/app-release.aab`

---

## 4. Keystore & Signing Configuration

Release builds automatically use the project release keystore if present at `android/keystore/docmorph-release-key.jks`.

### Environment Overrides for CI/CD
To customize signing keys during automated builds, pass environment variables:
```powershell
$env:DOCMORPH_KEYSTORE_PASSWORD = "your-keystore-password"
$env:DOCMORPH_KEY_ALIAS = "docmorph"
$env:DOCMORPH_KEY_PASSWORD = "your-key-password"
```

### Verification of Signature
Verify the integrity and APK signature scheme (v2/v3):
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\build-tools\35.0.0\apksigner.bat" verify --verbose android/app/build/outputs/apk/release/app-release.apk
```
Expected output:
```text
Verifies
Verified using v2 scheme (APK Signature Scheme v2): true
Number of signers: 1
```

---

## 5. Installing on Connected Android Device

### Install Debug APK
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r android/app/build/outputs/apk/debug/app-debug.apk
```

### Install Signed Release APK
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r android/app/build/outputs/apk/release/app-release.apk
```

### Launch Application
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am start -n com.docmorph.app/.MainActivity
```

