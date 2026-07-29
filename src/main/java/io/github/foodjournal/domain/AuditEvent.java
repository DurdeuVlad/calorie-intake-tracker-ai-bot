package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

/** Append-only security record. No mutators are intentionally provided. */
@Entity @Table(name = "audit_events")
public class AuditEvent {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @Column(nullable = false) private String actorType;
  @Column(nullable = false) private String actorIdentifier;
  @Column(nullable = false) private String action;
  private String targetType;
  private String targetIdentifier;
  private String reason;
  @Column(columnDefinition = "text") private String metadataSummary;
  @Column(nullable = false) private Instant occurredAt;
  protected AuditEvent() {}
  public AuditEvent(String actorType, String actorIdentifier, String action, String targetType, String targetIdentifier, String reason, String metadataSummary, Instant occurredAt) { this.actorType=actorType;this.actorIdentifier=actorIdentifier;this.action=action;this.targetType=targetType;this.targetIdentifier=targetIdentifier;this.reason=reason;this.metadataSummary=metadataSummary;this.occurredAt=occurredAt; }
  public Long getId(){return id;} public String getActorType(){return actorType;} public String getActorIdentifier(){return actorIdentifier;} public String getAction(){return action;} public String getTargetType(){return targetType;} public String getTargetIdentifier(){return targetIdentifier;} public String getReason(){return reason;} public String getMetadataSummary(){return metadataSummary;} public Instant getOccurredAt(){return occurredAt;}
}
