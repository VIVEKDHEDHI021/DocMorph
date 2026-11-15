# DOCMORPH — ANDROID RELEASE & DISTRIBUTION GUIDE

**Product:** DocMorph  
**Tagline:** Every document, personalized.  
**Target Platform:** Android (Google Play Store & Direct Distribution)  
**Package ID:** `com.docmorph.app`  
**Current Version:** 1.0 (Version Code 1)  
**Last Updated:** November 2026  

---

## 1. Release Artifacts Overview

DocMorph produces two primary release artifacts:

| Artifact | File Path | Target Audience | Signing |
| :--- | :--- | :--- | :--- |
| **Android App Bundle (AAB)** | `android/app/build/outputs/bundle/release/app-release.aab` | Google Play Console (Production/Internal Testing) | Signed (v2 Scheme) |
| **Signed Release APK** | `android/app/build/outputs/apk/release/app-release.apk` | Direct device testing, sideloading, enterprise distribution | Signed (v2 Scheme) |
| **Debug APK** | `android/app/build/outputs/apk/debug/app-debug.apk` | Local developer testing | Debug Keystore |

---

## 2. Release Checklist

Prior to publishing a release build, verify:

- [x] Application ID is stable: `com.docmorph.app`.
- [x] Version Name and Version Code are updated in `android/app/build.gradle`.
- [x] Minimum SDK is 22 (Android 5.1+), Target/Compile SDK is 34–36.
- [x] Android Manifest permissions are minimized (strictly `INTERNET`).
- [x] High-resolution adaptive icons and splash screen assets are bundled.
- [x] Backend CORS whitelists production Android origins (`capacitor://localhost`, `https://localhost`).
- [x] Production API endpoint (`VITE_API_URL`) points to a secure HTTPS server.
- [x] Release APK and AAB are signed with a secure release keystore.
- [x] Release keystores (`*.jks`, `*.keystore`) are excluded by `.gitignore`.
- [x] All 138 backend and frontend automated regression tests pass.

---

## 3. Keystore Security & Management

### 3.1 Generating a Production Keystore
If creating a new production keystore:
```powershell
keytool -genkeypair -v `
  -keystore android/keystore/docmorph-release-key.jks `
  -alias docmorph `
  -keyalg RSA `
  -keysize 2048 `
  -validity 10000 `
  -storepass "<STRONG_STORE_PASSWORD>" `
  -keypass "<STRONG_KEY_PASSWORD>" `
  -dname "CN=DocMorph, OU=Engineering, O=DocMorph, L=San Francisco, ST=CA, C=US"
```

### 3.2 Secure CI/CD Storage
Never check keystore files or passwords into Git. In CI/CD pipelines (e.g., GitHub Actions):
1. Store the `.jks` file as a Base64-encoded GitHub Secret (`ANDROID_KEYSTORE_BASE64`).
2. Store passwords as GitHub Secrets:
   - `DOCMORPH_KEYSTORE_PASSWORD`
   - `DOCMORPH_KEY_ALIAS`
   - `DOCMORPH_KEY_PASSWORD`
3. Decode the keystore during the CI build step into `android/keystore/docmorph-release-key.jks`.

---

## 4. Google Play Console Publishing Procedure

### Step 1: Create Application Entry
1. Open [Google Play Console](https://play.google.com/console).
2. Select **Create app**.
3. App name: `DocMorph`.
4. Default language: `English (United States)`.
5. App or game: `App`.
6. Free or paid: `Free`.

### Step 2: Data Safety Declarations
DocMorph is designed with privacy-first, account-free architecture:
- **Personal Info:** Student name and enrollment number are collected for academic document personalization.
  - Data is stored **locally on the user's device**.
  - Transmitted to the server solely to execute the requested personalization operation.
  - Documents and temporary processing records are isolated to the anonymous session and cleared.
- **Third-Party Sharing:** No data is shared with third parties or advertising networks.
- **Security Practices:** Data in transit is encrypted using HTTPS (TLS 1.3).

### Step 3: Upload Release Bundle
1. Navigate to **Release > Production** (or **Internal testing**).
2. Create a new release.
3. Upload `android/app/build/outputs/bundle/release/app-release.aab`.
4. Provide release notes highlighting the account-free, native PDF personalization workflow.
5. Review and rollout.

---

## 5. Direct Sideloading & Testing

For testing on real devices without Google Play:
1. Enable **Developer Options** and **USB Debugging** on the Android device.
2. Connect via USB or Wi-Fi adb:
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices
   ```
3. Install the signed release APK:
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r android/app/build/outputs/apk/release/app-release.apk
   ```
4. Verify the application launches, prompts for profile setup, and executes personalization seamlessly.

