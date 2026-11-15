package com.docmorph.app.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Manages sensitive student profile data using Android Keystore backed EncryptedSharedPreferences.
 */
class SecureProfileManager(context: Context) {

    private val masterKey: MasterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val sharedPreferences: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        PREFS_FILENAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveProfile(
        fullName: String,
        enrollmentNumber: String,
        rollNumber: String? = null,
        studentId: String? = null
    ) {
        sharedPreferences.edit()
            .putString(KEY_FULL_NAME, fullName.trim())
            .putString(KEY_ENROLLMENT_NUMBER, enrollmentNumber.trim())
            .putString(KEY_ROLL_NUMBER, rollNumber?.trim())
            .putString(KEY_STUDENT_ID, studentId?.trim())
            .putLong(KEY_UPDATED_AT, System.currentTimeMillis())
            .apply()
    }

    fun getProfile(): Map<String, String?>? {
        val fullName = sharedPreferences.getString(KEY_FULL_NAME, null)
        val enrollmentNumber = sharedPreferences.getString(KEY_ENROLLMENT_NUMBER, null)
        if (fullName.isNullOrBlank() || enrollmentNumber.isNullOrBlank()) {
            return null
        }

        return mapOf(
            "fullName" to fullName,
            "enrollmentNumber" to enrollmentNumber,
            "rollNumber" to sharedPreferences.getString(KEY_ROLL_NUMBER, null),
            "studentId" to sharedPreferences.getString(KEY_STUDENT_ID, null),
            "updatedAt" to sharedPreferences.getLong(KEY_UPDATED_AT, 0L).toString()
        )
    }

    fun deleteProfile() {
        sharedPreferences.edit().clear().apply()
    }

    fun hasProfile(): Boolean {
        val fullName = sharedPreferences.getString(KEY_FULL_NAME, null)
        val enrollmentNumber = sharedPreferences.getString(KEY_ENROLLMENT_NUMBER, null)
        return !fullName.isNullOrBlank() && !enrollmentNumber.isNullOrBlank()
    }

    companion object {
        private const val PREFS_FILENAME = "docmorph_secure_profile"
        private const val KEY_FULL_NAME = "full_name"
        private const val KEY_ENROLLMENT_NUMBER = "enrollment_number"
        private const val KEY_ROLL_NUMBER = "roll_number"
        private const val KEY_STUDENT_ID = "student_id"
        private const val KEY_UPDATED_AT = "updated_at"
    }
}

