import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "dummy_firebase_api_key",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "ai-art-director-prod.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "ai-art-director-prod",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "ai-art-director-prod.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "1012864945903",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:1012864945903:web:b35b58a3248ad9ff10551a",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-Q7243Y8D0H"
};

const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

export { app, auth, googleProvider, firebaseConfig };
