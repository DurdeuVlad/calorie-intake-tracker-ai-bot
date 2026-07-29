package io.github.foodjournal.admin.auth;

public interface AdminAuditService {
  void record(String actorType, String actorId, String action, String targetType, String targetId);
}
