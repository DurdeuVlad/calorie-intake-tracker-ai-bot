import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { validateEmail, validatePassword } from '../auth/validation';

export interface AuthFormProps {
  submitLabel: string;
  loading?: boolean;
  /** Server-side error to surface above the button (e.g. "invalid email or password"). */
  error?: string | null;
  onSubmit(email: string, password: string): void;
}

export function AuthForm({ submitLabel, loading = false, error, onSubmit }: AuthFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const handleSubmit = () => {
    const nextEmailError = validateEmail(email);
    const nextPasswordError = validatePassword(password);
    setEmailError(nextEmailError);
    setPasswordError(nextPasswordError);
    if (nextEmailError || nextPasswordError) return;
    onSubmit(email, password);
  };

  return (
    <View style={styles.form}>
      <TextInput
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        textContentType="emailAddress"
        editable={!loading}
        value={email}
        onChangeText={setEmail}
        testID="email-input"
      />
      {emailError ? (
        <Text style={styles.fieldError} testID="email-error">
          {emailError}
        </Text>
      ) : null}

      <TextInput
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        textContentType="password"
        editable={!loading}
        value={password}
        onChangeText={setPassword}
        testID="password-input"
      />
      {passwordError ? (
        <Text style={styles.fieldError} testID="password-error">
          {passwordError}
        </Text>
      ) : null}

      {error ? (
        <Text style={styles.serverError} testID="server-error">
          {error}
        </Text>
      ) : null}

      <Pressable
        style={[styles.button, loading && styles.buttonDisabled]}
        disabled={loading}
        onPress={handleSubmit}
        accessibilityRole="button"
        testID="submit-button"
      >
        {loading ? (
          <ActivityIndicator color="#fff" testID="submit-spinner" />
        ) : (
          <Text style={styles.buttonText}>{submitLabel}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: 12, width: '100%' },
  input: {
    borderWidth: 1,
    borderColor: '#c8c8ce',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  fieldError: { color: '#b3261e', fontSize: 13, marginTop: -6 },
  serverError: { color: '#b3261e', fontSize: 14, textAlign: 'center' },
  button: {
    backgroundColor: '#1a6ef5',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
