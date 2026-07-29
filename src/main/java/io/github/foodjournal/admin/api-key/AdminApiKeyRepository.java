package io.github.foodjournal.admin.api_key;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
public interface AdminApiKeyRepository extends JpaRepository<AdminApiKey, Long> { Optional<AdminApiKey> findByKeyHash(String keyHash); }
