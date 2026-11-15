# DocMorph ProGuard / R8 Rules for Offline Android Production Build

# 1. Capacitor Bridge & Custom Native Plugins
-keep class com.docmorph.app.plugin.** { *; }
-keepclassmembers class * {
    @com.getcapacitor.annotation.CapacitorPlugin *;
    @com.getcapacitor.PluginMethod public *;
}
-keep class com.getcapacitor.** { *; }
-dontwarn com.getcapacitor.**

# 2. Android Room Database & Entities
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Dao interface * { *; }
-keep class com.docmorph.app.db.** { *; }
-keepclassmembers class com.docmorph.app.db.** { *; }
-dontwarn androidx.room.paging.**

# 3. Microsoft ONNX Runtime Mobile
-keep class ai.onnxruntime.** { *; }
-dontwarn ai.onnxruntime.**

# 4. Google ML Kit Text Recognition (Bundled Offline)
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**
-keep class com.google.android.gms.internal.mlkit_vision_text_common.** { *; }
-dontwarn com.google.android.gms.internal.mlkit_vision_text_common.**

# 5. PDFBox-Android & BouncyCastle
-keep class com.tom_roush.pdfbox.** { *; }
-dontwarn com.tom_roush.pdfbox.**
-keep class org.bouncycastle.** { *; }
-dontwarn org.bouncycastle.**

# 6. AndroidX Security Crypto (Android Keystore EncryptedSharedPreferences)
-keep class androidx.security.crypto.** { *; }
-dontwarn androidx.security.crypto.**

# 7. Kotlin Coroutines & JSON serialization
-keepclassmembers class kotlinx.coroutines.** { *; }
-dontwarn kotlinx.coroutines.**
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# 8. Keep line numbers for actionable stack traces
-keepattributes SourceFile,LineNumberTable
