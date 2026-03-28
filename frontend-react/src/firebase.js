import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "AIzaSyDTZgrSFvtKqhvQCBV_-DUY6UDyRNbM1Ak",
  authDomain: "secret-medium-491502-n8.firebaseapp.com",
  projectId: "secret-medium-491502-n8",
  storageBucket: "secret-medium-491502-n8.firebasestorage.app",
  messagingSenderId: "188966768344",
  appId: "1:188966768344:web:255384941a370acbf7d1ad",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export default app;
