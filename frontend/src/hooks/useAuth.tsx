import React, { createContext, useContext, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { User, StudentProfile } from '../types';
import { profileStorage } from '../services/profileStorage';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName?: string) => Promise<void>;
  loginAsDevGuest: () => Promise<void>;
  initializeAnonymousSession: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function createLocalUser(profile: StudentProfile | null): User {
  return {
    id: 'device_owner',
    email: 'offline@device.local',
    full_name: profile?.full_name || 'Device Owner',
    is_active: true,
    created_at: profile?.created_at || new Date(0).toISOString(),
  };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    // Load local student profile without any network calls
    profileStorage.getProfile().then((profile) => {
      if (isMounted) {
        setUser(createLocalUser(profile));
        setIsLoading(false);
      }
    }).catch(() => {
      if (isMounted) {
        setUser(createLocalUser(null));
        setIsLoading(false);
      }
    });

    // Reactively update user info when local profile updates
    const unsubscribe = profileStorage.onProfileChange((updatedProfile) => {
      setUser(createLocalUser(updatedProfile));
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  const login = async (_email: string, _password: string) => {
    // 100% offline: no-op, user is always authenticated locally
    queryClient.clear();
    const p = await profileStorage.getProfile();
    setUser(createLocalUser(p));
  };

  const signup = async (_email: string, _password: string, fullName?: string) => {
    queryClient.clear();
    if (fullName) {
      const existing = await profileStorage.getProfile();
      await profileStorage.saveProfile({
        full_name: fullName,
        enrollment_number: existing?.enrollment_number || 'PENDING',
        roll_number: existing?.roll_number,
        student_id: existing?.student_id,
      });
    }
    const p = await profileStorage.getProfile();
    setUser(createLocalUser(p));
  };

  const initializeAnonymousSession = async () => {
    // 100% offline: no server call
    queryClient.clear();
    const p = await profileStorage.getProfile();
    setUser(createLocalUser(p));
  };

  const loginAsDevGuest = async () => {
    await initializeAnonymousSession();
  };

  const logout = async () => {
    // Local app reset
    queryClient.clear();
    const p = await profileStorage.getProfile();
    setUser(createLocalUser(p));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: true,
        login,
        signup,
        loginAsDevGuest,
        initializeAnonymousSession,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

