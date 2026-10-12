import { Link } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../../api/errors';
import { useAuth } from '../../auth/AuthContext';
import { AuthForm } from '../../components/AuthForm';

export default function SignupScreen() {
  const { signUp } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (email: string, password: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await signUp(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.inner}>
          <Text style={styles.title}>Create account</Text>
          <Text style={styles.subtitle}>Sign up with email and password</Text>
          <AuthForm
            submitLabel="Create account"
            loading={submitting}
            error={error}
            onSubmit={handleSubmit}
          />
          <Link href="/(auth)/login" style={styles.link}>
            Already have an account? Sign in
          </Link>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { flex: 1 },
  inner: { flex: 1, justifyContent: 'center', paddingHorizontal: 24, gap: 16 },
  title: { fontSize: 28, fontWeight: '700', textAlign: 'center' },
  subtitle: { fontSize: 15, color: '#5b5b62', textAlign: 'center', marginBottom: 8 },
  link: { color: '#1a6ef5', textAlign: 'center', fontSize: 15, paddingVertical: 8 },
});
