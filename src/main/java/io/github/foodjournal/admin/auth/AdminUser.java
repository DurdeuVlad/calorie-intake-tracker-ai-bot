package io.github.foodjournal.admin.auth;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "admin_users")
public class AdminUser {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @Column(nullable = false, unique = true, length = 320) private String email;
  @Column(name = "password_hash", nullable = false, length = 255) private String passwordHash;
  @Column(nullable = false) private boolean enabled = true;
  @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
  @Column(name = "last_login_at") private Instant lastLoginAt;
  protected AdminUser() {}
  public AdminUser(String email, String passwordHash) { this.email = email; this.passwordHash = passwordHash; }
  public Long getId() { return id; }
  public String getEmail() { return email; }
  public String getPasswordHash() { return passwordHash; }
  public boolean isEnabled() { return enabled; }
  public void markLoggedIn() { lastLoginAt = Instant.now(); }
}
