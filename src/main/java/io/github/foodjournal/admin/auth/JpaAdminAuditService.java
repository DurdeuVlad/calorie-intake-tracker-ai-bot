package io.github.foodjournal.admin.auth;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class JpaAdminAuditService implements AdminAuditService {
  private final AdminAuditEventRepository events;
  public JpaAdminAuditService(AdminAuditEventRepository events) { this.events = events; }
  @Override @Transactional(propagation = Propagation.REQUIRES_NEW)
  public void record(String actorType, String actorId, String action, String targetType, String targetId) {
    events.save(new AdminAuditEvent(actorType, actorId, action, targetType, targetId));
  }
}
