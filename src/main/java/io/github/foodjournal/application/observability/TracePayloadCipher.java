package io.github.foodjournal.application.observability;

/**
 * Encryption boundary for user-facing trace evidence. Implementations must use authenticated
 * encryption and must never log plaintext or keys. If no implementation is installed, payload
 * persistence is disabled rather than storing plaintext.
 */
public interface TracePayloadCipher {
  String encrypt(String plaintext);
  String decrypt(String ciphertext);
}
