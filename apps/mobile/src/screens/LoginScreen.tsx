/** Login screen with Google OAuth. */

import React from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { useAuth } from '../hooks/useAuth';

export function LoginScreen() {
  const { signIn, isLoading, error } = useAuth();

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <Text style={styles.logo}>EHA</Text>
        <Text style={styles.tagline}>Email Helper Agent</Text>
        <Text style={styles.description}>
          Smart email notifications, AI-powered replies, and calendar
          integration — all under your control.
        </Text>
      </View>

      <View style={styles.bottom}>
        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity
          style={styles.googleButton}
          onPress={signIn}
          disabled={isLoading}
          activeOpacity={0.8}
        >
          {isLoading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.googleButtonText}>Sign in with Google</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.privacy}>
          EHA never sends emails automatically. Your data stays encrypted and
          under your control.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    justifyContent: 'space-between',
    padding: 32,
  },
  hero: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logo: {
    fontSize: 56,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: 4,
  },
  tagline: {
    fontSize: 18,
    color: '#a0a0c0',
    marginTop: 8,
  },
  description: {
    fontSize: 14,
    color: '#7070a0',
    textAlign: 'center',
    marginTop: 24,
    lineHeight: 22,
    paddingHorizontal: 16,
  },
  bottom: {
    paddingBottom: 20,
  },
  error: {
    color: '#ff6b6b',
    textAlign: 'center',
    marginBottom: 16,
    fontSize: 14,
  },
  googleButton: {
    backgroundColor: '#4285F4',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  googleButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  privacy: {
    fontSize: 11,
    color: '#5050a0',
    textAlign: 'center',
    marginTop: 16,
    lineHeight: 16,
  },
});
