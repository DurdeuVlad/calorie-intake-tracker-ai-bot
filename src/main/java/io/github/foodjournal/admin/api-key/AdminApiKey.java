package io.github.foodjournal.admin.api_key;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.Set;

@Entity @Table(name = "admin_api_keys")
public class AdminApiKey {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @Column(nullable=false, length=120) private String name;
  @Column(name="key_prefix", nullable=false, length=32) private String keyPrefix;
  @Column(name="key_hash", nullable=false, unique=true, length=64) private String keyHash;
  @Column(nullable=false) private String scopes;
  @Column(name="expires_at") private Instant expiresAt;
  @Column(name="revoked_at") private Instant revokedAt;
  @Column(name="created_at", nullable=false) private Instant createdAt = Instant.now();
  @Column(name="last_used_at") private Instant lastUsedAt;
  protected AdminApiKey() {}
  public AdminApiKey(String name, String keyPrefix, String keyHash, Set<ApiKeyScope> scopes, Instant expiresAt) { this.name=name; this.keyPrefix=keyPrefix; this.keyHash=keyHash; this.scopes=ApiKeyScope.serialize(scopes); this.expiresAt=expiresAt; }
  public Long getId() { return id; } public String getName() { return name; } public String getKeyPrefix() { return keyPrefix; } public Instant getExpiresAt() { return expiresAt; } public Instant getRevokedAt() { return revokedAt; }
  public Set<ApiKeyScope> scopes() { return ApiKeyScope.parse(scopes); }
  public boolean isActive(Instant now) { return revokedAt == null && (expiresAt == null || expiresAt.isAfter(now)); }
  public void revoke() { revokedAt = Instant.now(); }
  public void markUsed() { lastUsedAt = Instant.now(); }
}
