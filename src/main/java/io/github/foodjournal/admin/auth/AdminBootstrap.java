package io.github.foodjournal.admin.auth;

import io.github.foodjournal.config.AdminProperties;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class AdminBootstrap implements ApplicationRunner {
  private final AdminUserRepository users; private final PasswordEncoder passwords; private final AdminProperties properties; private final AdminAuditService audit;
  public AdminBootstrap(AdminUserRepository users, PasswordEncoder passwords, AdminProperties properties, AdminAuditService audit) { this.users=users; this.passwords=passwords; this.properties=properties; this.audit=audit; }
  @Override @Transactional public void run(ApplicationArguments arguments) {
    if (properties.bootstrapEmail().isBlank() || properties.bootstrapPassword().isBlank() || users.count() != 0) return;
    AdminUser user = users.save(new AdminUser(properties.bootstrapEmail(), passwords.encode(properties.bootstrapPassword())));
    audit.record("SYSTEM", null, "ADMIN_BOOTSTRAPPED", "ADMIN_USER", user.getId().toString());
  }
}
