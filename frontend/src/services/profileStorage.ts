/**
 * Persistent Profile Storage Service for DocMorph.
 *
 * Implements an account-free, device-isolated storage abstraction for student credentials:
 * Full Name, Enrollment Number, Roll Number, and Student ID.
 *
 * On native Android, delegates to DocMorphNative (Android Keystore + EncryptedSharedPreferences).
 * On web/preview, falls back to localStorage.
 */

import { StudentProfile } from '../types';
import { DocMorphNative, isNativePlatform } from './nativeDocMorph';

const STORAGE_KEY = 'docmorph_student_profile';
const PROFILE_UPDATED_EVENT = 'docmorph_profile_updated';

class ProfileStorageService {
  private inMemoryProfile: StudentProfile | null = null;
  private isLoaded = false;

  /**
   * Retrieves the saved student profile from persistent storage.
   */
  async getProfile(): Promise<StudentProfile | null> {
    if (this.isLoaded && this.inMemoryProfile) {
      return this.inMemoryProfile;
    }

    try {
      if (isNativePlatform()) {
        const res = await DocMorphNative.getProfile();
        if (res.hasProfile && res.profile) {
          const profile: StudentProfile = {
            full_name: res.profile.fullName,
            enrollment_number: res.profile.enrollmentNumber,
            roll_number: res.profile.rollNumber || null,
            student_id: res.profile.studentId || null,
            created_at: res.profile.updatedAt ? new Date(Number(res.profile.updatedAt)).toISOString() : new Date().toISOString(),
            updated_at: res.profile.updatedAt ? new Date(Number(res.profile.updatedAt)).toISOString() : new Date().toISOString(),
          };
          this.inMemoryProfile = profile;
          this.isLoaded = true;
          return profile;
        }
      } else {
        // Fallback to localStorage for web
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as StudentProfile;
          if (parsed.full_name && parsed.enrollment_number) {
            this.inMemoryProfile = parsed;
            this.isLoaded = true;
            return parsed;
          }
        }
      }
    } catch (e) {
      console.warn('Failed to get student profile from storage:', e);
    }

    this.isLoaded = true;
    return null;
  }

  /**
   * Saves or updates the student profile persistently.
   */
  async saveProfile(profile: Omit<StudentProfile, 'created_at' | 'updated_at'>): Promise<StudentProfile> {
    const existing = await this.getProfile();
    const now = new Date().toISOString();

    const fullProfile: StudentProfile = {
      full_name: profile.full_name.trim(),
      enrollment_number: profile.enrollment_number.trim(),
      roll_number: profile.roll_number?.trim() || null,
      student_id: profile.student_id?.trim() || null,
      created_at: existing?.created_at || now,
      updated_at: now,
    };

    if (isNativePlatform()) {
      await DocMorphNative.saveProfile({
        fullName: fullProfile.full_name,
        enrollmentNumber: fullProfile.enrollment_number,
        rollNumber: fullProfile.roll_number || undefined,
        studentId: fullProfile.student_id || undefined,
      });
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(fullProfile));
    }

    this.inMemoryProfile = fullProfile;
    this.isLoaded = true;

    // Dispatch custom event for live UI reactivity
    window.dispatchEvent(new CustomEvent(PROFILE_UPDATED_EVENT, { detail: fullProfile }));

    return fullProfile;
  }

  /**
   * Deletes the student profile from device storage.
   */
  async deleteProfile(): Promise<void> {
    if (isNativePlatform()) {
      await DocMorphNative.deleteProfile();
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }

    this.inMemoryProfile = null;
    this.isLoaded = true;
    window.dispatchEvent(new CustomEvent(PROFILE_UPDATED_EVENT, { detail: null }));
  }

  /**
   * Checks whether a valid student profile is configured on the device.
   */
  async hasProfile(): Promise<boolean> {
    const profile = await this.getProfile();
    return Boolean(profile && profile.full_name && profile.enrollment_number);
  }

  /**
   * Subscribes to profile update/deletion events.
   */
  onProfileChange(callback: (profile: StudentProfile | null) => void): () => void {
    const listener = (event: Event) => {
      const custom = event as CustomEvent<StudentProfile | null>;
      callback(custom.detail);
    };

    window.addEventListener(PROFILE_UPDATED_EVENT, listener);
    return () => window.removeEventListener(PROFILE_UPDATED_EVENT, listener);
  }
}

export const profileStorage = new ProfileStorageService();
