package io.github.foodjournal.admin.auth;

import org.springframework.data.jpa.repository.JpaRepository;
public interface AdminAuditEventRepository extends JpaRepository<AdminAuditEvent, Long> {}
