package io.github.foodjournal.admin.api_key;

import io.github.foodjournal.admin.auth.AdminAuditService;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.Optional;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ApiKeyService {
  private static final SecureRandom RANDOM = new SecureRandom();
  private final AdminApiKeyRepository keys; private final AdminAuditService audit;
  public ApiKeyService(AdminApiKeyRepository keys, AdminAuditService audit) { this.keys=keys; this.audit=audit; }
  @Transactional public IssuedApiKey issue(String name, Set<ApiKeyScope> scopes, Instant expiresAt, String actorId) {
    if (name == null || name.isBlank() || name.length() > 120 || scopes == null || scopes.isEmpty()) throw new IllegalArgumentException("A name and at least one scope are required");
    if (expiresAt != null && !expiresAt.isAfter(Instant.now())) throw new IllegalArgumentException("Expiry must be in the future");
    byte[] entropy = new byte[32]; RANDOM.nextBytes(entropy);
    String plaintext = "fj_" + Base64.getUrlEncoder().withoutPadding().encodeToString(entropy);
    AdminApiKey key = keys.save(new AdminApiKey(name.trim(), plaintext.substring(0, Math.min(15, plaintext.length())), hash(plaintext), scopes, expiresAt));
    audit.record("ADMIN", actorId, "API_KEY_CREATED", "API_KEY", key.getId().toString());
    return new IssuedApiKey(key.getId(), key.getName(), key.getKeyPrefix(), plaintext);
  }
  @Transactional public Optional<ApiKeyPrincipal> authenticate(String plaintext) {
    if (plaintext == null || plaintext.isBlank() || plaintext.length() > 256) return Optional.empty();
    return keys.findByKeyHash(hash(plaintext)).filter(key -> key.isActive(Instant.now())).map(key -> {
      key.markUsed(); audit.record("API_KEY", key.getId().toString(), "API_KEY_USED", "API_KEY", key.getId().toString());
      return new ApiKeyPrincipal(key.getId(), key.getName(), key.scopes());
    });
  }
  @Transactional public void revoke(long id, String actorId) {
    AdminApiKey key = keys.findById(id).orElseThrow(() -> new IllegalArgumentException("API key not found"));
    if (key.getRevokedAt() == null) { key.revoke(); audit.record("ADMIN", actorId, "API_KEY_REVOKED", "API_KEY", Long.toString(id)); }
  }
  @Transactional(readOnly=true) public java.util.List<AdminApiKey> list() { return keys.findAll(org.springframework.data.domain.Sort.by(org.springframework.data.domain.Sort.Direction.DESC,"id")); }
  static String hash(String key) {
    try { return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8))); }
    catch (java.security.NoSuchAlgorithmException exception) { throw new IllegalStateException("SHA-256 unavailable", exception); }
  }
}
