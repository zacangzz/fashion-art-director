import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { auth, googleProvider } from "../config/firebase";
import { fetchCurrentUserProfile } from "../services/apiClient";

const AuthContext = createContext({
  currentUser: null,
  userProfile: null,
  loading: true,
  isDevBypass: false,
  signInWithGoogle: async () => {},
  signInWithEmail: async () => {},
  signUpWithEmail: async () => {},
  signOutUser: async () => {},
  quickDevLogin: async () => {},
  refreshUserProfile: async () => {},
  getIdToken: async () => null,
});

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [userProfile, setUserProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isDevBypass, setIsDevBypass] = useState(() => localStorage.getItem("dev_bypass_auth") === "true");

  const syncUserProfile = useCallback(async (user) => {
    if (!user && !localStorage.getItem("dev_bypass_auth")) {
      setUserProfile(null);
      return;
    }
    try {
      const profile = await fetchCurrentUserProfile();
      setUserProfile(profile);
    } catch (err) {
      console.warn("Failed to fetch user profile:", err);
      // Fallback profile if backend unreachable
      if (user) {
        setUserProfile({
          id: user.uid,
          uid: user.uid,
          email: user.email,
          display_name: user.displayName || user.email?.split("@")[0] || "Studio User",
          photo_url: user.photoURL,
          role: "user",
          status: "pending_invite",
          is_approved: false,
          is_admin: false,
        });
      }
    }
  }, []);

  useEffect(() => {
    // Check if dev bypass active
    if (localStorage.getItem("dev_bypass_auth") === "true") {
      const devUser = {
        uid: "local_dev_user",
        email: "developer@local.studio",
        displayName: "Local Developer",
        photoURL: null,
      };
      setCurrentUser(devUser);
      setIsDevBypass(true);
      syncUserProfile(devUser).finally(() => setLoading(false));
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setCurrentUser(user);
      if (user) {
        await syncUserProfile(user);
      } else {
        setUserProfile(null);
      }
      setLoading(false);
    });

    return unsubscribe;
  }, [syncUserProfile]);

  const signInWithGoogle = async () => {
    localStorage.removeItem("dev_bypass_auth");
    setIsDevBypass(false);
    const result = await signInWithPopup(auth, googleProvider);
    setCurrentUser(result.user);
    await syncUserProfile(result.user);
    return result;
  };

  const signInWithEmail = async (email, password) => {
    localStorage.removeItem("dev_bypass_auth");
    setIsDevBypass(false);
    const result = await signInWithEmailAndPassword(auth, email, password);
    setCurrentUser(result.user);
    await syncUserProfile(result.user);
    return result;
  };

  const signUpWithEmail = async (email, password) => {
    localStorage.removeItem("dev_bypass_auth");
    setIsDevBypass(false);
    const result = await createUserWithEmailAndPassword(auth, email, password);
    setCurrentUser(result.user);
    await syncUserProfile(result.user);
    return result;
  };

  const quickDevLogin = async () => {
    localStorage.setItem("dev_bypass_auth", "true");
    setIsDevBypass(true);
    const devUser = {
      uid: "local_dev_user",
      email: "developer@local.studio",
      displayName: "Local Developer",
      photoURL: null,
    };
    setCurrentUser(devUser);
    await syncUserProfile(devUser);
    setLoading(false);
  };

  const signOutUser = async () => {
    localStorage.removeItem("dev_bypass_auth");
    setIsDevBypass(false);
    try {
      if (auth.currentUser) {
        await signOut(auth);
      }
    } catch (err) {
      console.warn("Sign out error:", err);
    }
    setCurrentUser(null);
    setUserProfile(null);
  };

  const refreshUserProfile = async () => {
    await syncUserProfile(currentUser);
  };

  const getIdToken = async () => {
    if (isDevBypass) return "local_dev_token";
    if (!currentUser) return null;
    return currentUser.getIdToken ? currentUser.getIdToken() : "local_dev_token";
  };

  const value = {
    currentUser,
    userProfile,
    loading,
    isDevBypass,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    signOutUser,
    quickDevLogin,
    refreshUserProfile,
    getIdToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
