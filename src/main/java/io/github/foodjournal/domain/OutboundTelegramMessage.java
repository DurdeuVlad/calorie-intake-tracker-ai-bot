package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name="outbound_telegram_messages")
public class OutboundTelegramMessage {
  public enum Status { PENDING, IN_PROGRESS, SENT }
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
  @Column(nullable=false) private long chatId;
  @Column(nullable=false, columnDefinition="text") private String text;
  @Enumerated(EnumType.STRING) @Column(nullable=false) private Status status=Status.PENDING;
  @Column(nullable=false) private int attempts=0;
  @Column(nullable=false) private Instant nextAttemptAt=Instant.now();
  private Instant leaseExpiresAt;
  @Column(nullable=false) private Instant createdAt=Instant.now();
  private Instant sentAt;
  protected OutboundTelegramMessage() {}
  public OutboundTelegramMessage(long chatId,String text){this.chatId=chatId;this.text=text;}
  public Long getId(){return id;} public long getChatId(){return chatId;} public String getText(){return text;} public Status getStatus(){return status;}
  public void claim(){status=Status.IN_PROGRESS;leaseExpiresAt=Instant.now().plusSeconds(60);}
  public void markSent(){status=Status.SENT;sentAt=Instant.now();leaseExpiresAt=null;}
  public void scheduleRetry(){status=Status.PENDING;leaseExpiresAt=null;attempts++;nextAttemptAt=Instant.now().plusSeconds(Math.min(300, 1L << Math.min(attempts, 8)));}
}
