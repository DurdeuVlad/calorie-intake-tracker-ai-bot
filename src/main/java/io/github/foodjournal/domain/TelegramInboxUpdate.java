package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

/** Durable, ordered inbox. Payload is deleted once processing succeeds. */
@Entity @Table(name="telegram_update_inbox")
public class TelegramInboxUpdate {
  public enum Status { PENDING, IN_PROGRESS, COMPLETED, FAILED }
  @Id @Column(name="update_id") private Long updateId;
  @Column(name="telegram_user_id", nullable=false) private long telegramUserId;
  @Column(name="chat_id", nullable=false) private long chatId;
  @Column(nullable=false, columnDefinition="text") private String payload;
  @Enumerated(EnumType.STRING) @Column(nullable=false) private Status status=Status.PENDING;
  @Column(nullable=false) private int attempts;
  @Column(nullable=false) private Instant nextAttemptAt=Instant.now();
  private Instant leaseExpiresAt; private UUID leaseToken;
  @Column(nullable=false) private UUID correlationId=UUID.randomUUID();
  private String lastErrorCategory;
  @Column(nullable=false) private Instant createdAt=Instant.now(); private Instant completedAt;
  protected TelegramInboxUpdate() {}
  public TelegramInboxUpdate(long updateId,long userId,long chatId,String payload){this.updateId=updateId;telegramUserId=userId;this.chatId=chatId;this.payload=payload;}
  public Long getUpdateId(){return updateId;} public long getTelegramUserId(){return telegramUserId;} public long getChatId(){return chatId;} public String getPayload(){return payload;} public Status getStatus(){return status;} public UUID getLeaseToken(){return leaseToken;} public UUID getCorrelationId(){return correlationId;} public String getLastErrorCategory(){return lastErrorCategory;}
  public void claim(){status=Status.IN_PROGRESS;leaseToken=UUID.randomUUID();leaseExpiresAt=Instant.now().plusSeconds(90);}
  public void complete(UUID token){if(!token.equals(leaseToken))return;status=Status.COMPLETED;payload="";completedAt=Instant.now();leaseToken=null;leaseExpiresAt=null;lastErrorCategory=null;}
  public void retry(UUID token,String category){if(!token.equals(leaseToken))return;attempts++;status=attempts>=3?Status.FAILED:Status.PENDING;lastErrorCategory=category;leaseToken=null;leaseExpiresAt=null;nextAttemptAt=Instant.now().plusSeconds(Math.min(300,1L<<Math.min(attempts,8)));if(status==Status.FAILED){payload="";completedAt=Instant.now();}}
}
