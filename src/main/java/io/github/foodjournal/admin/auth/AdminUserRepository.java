package io.github.foodjournal.admin.auth;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AdminUserRepository extends JpaRepository<AdminUser, Long> {
  Optional<AdminUser> findByEmailIgnoreCase(String email);
}
