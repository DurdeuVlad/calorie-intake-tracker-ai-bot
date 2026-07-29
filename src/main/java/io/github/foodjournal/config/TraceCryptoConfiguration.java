package io.github.foodjournal.config;

import io.github.foodjournal.application.observability.TracePayloadCipher;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class TraceCryptoConfiguration {
  @Bean TracePayloadCipher tracePayloadCipher(AdminProperties properties) {
    if (properties.traceEncryptionKey().isBlank()) return null;
    byte[] key;
    try { key=Base64.getDecoder().decode(properties.traceEncryptionKey()); }
    catch (IllegalArgumentException badKey) { throw new IllegalStateException("ADMIN_TRACE_ENCRYPTION_KEY must be base64", badKey); }
    if (key.length != 32) throw new IllegalStateException("ADMIN_TRACE_ENCRYPTION_KEY must decode to 32 bytes");
    return new AesGcmCipher(key);
  }
  private static final class AesGcmCipher implements TracePayloadCipher {
    private static final SecureRandom RANDOM=new SecureRandom(); private final SecretKeySpec key;
    AesGcmCipher(byte[] bytes){key=new SecretKeySpec(bytes,"AES");}
    public String encrypt(String plaintext){try{byte[] nonce=new byte[12];RANDOM.nextBytes(nonce);Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key,new GCMParameterSpec(128,nonce));byte[] payload=c.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));byte[] all=new byte[nonce.length+payload.length];System.arraycopy(nonce,0,all,0,nonce.length);System.arraycopy(payload,0,all,nonce.length,payload.length);return Base64.getEncoder().encodeToString(all);}catch(Exception e){throw new IllegalStateException("Could not encrypt trace payload",e);}}
    public String decrypt(String ciphertext){try{byte[] all=Base64.getDecoder().decode(ciphertext);if(all.length<29)throw new IllegalArgumentException("Invalid trace payload");byte[] nonce=java.util.Arrays.copyOfRange(all,0,12);Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,nonce));return new String(c.doFinal(all,12,all.length-12),StandardCharsets.UTF_8);}catch(Exception e){throw new IllegalStateException("Could not decrypt trace payload",e);}}
  }
}
