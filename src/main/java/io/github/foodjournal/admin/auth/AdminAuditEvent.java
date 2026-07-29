package io.github.foodjournal.admin.auth;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "admin_audit_events")
public class AdminAuditEvent {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @Column(name = "occurred_at", nullable = false) private Instant occurredAt = Instant.now();
  @Column(name = "actor_type", nullable = false, length = 32) private String actorType;
  @Column(name = "actor_id") private String actorId;
  @Column(nullable = false, length = 96) private String action;
  @Column(name = "target_type", length = 64) private String targetType;
  @Column(name = "target_id") private String targetId;
  @Column(name = "correlation_id") private java.util.UUID correlationId;
  @Column(nullable = false) private String metadata = "{}";
  protected AdminAuditEvent() {}
  public AdminAuditEvent(String actorType, String actorId, String action, String targetType, String targetId) {
    this.actorType = actorType; this.actorId = actorId; this.action = action; this.targetType = targetType; this.targetId = targetId;
  }
}
