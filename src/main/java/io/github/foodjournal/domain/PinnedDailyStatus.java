package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;
import java.util.UUID;

@Entity
@Table(name="pinned_daily_status", uniqueConstraints=@UniqueConstraint(columnNames={"user_id","chat_id"}))
public class PinnedDailyStatus {
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
  @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
  @Column(name="chat_id", nullable=false) private long chatId;
  @Column(name="local_date", nullable=false) private LocalDate localDate;
  @Column(name="desired_text", nullable=false, columnDefinition="text") private String desiredText;
  @Column(name="desired_version", nullable=false) private long desiredVersion=1;
  @Column(name="delivered_version", nullable=false) private long deliveredVersion=0;
  @Column(name="telegram_message_id") private Long telegramMessageId;
  @Column(name="updated_at", nullable=false) private Instant updatedAt=Instant.now();
  @Enumerated(EnumType.STRING) @Column(nullable=false) private Status status=Status.PENDING;
  private Instant leaseExpiresAt; private UUID leaseToken;
  public enum Status { PENDING, IN_PROGRESS }
  protected PinnedDailyStatus() {}
  public PinnedDailyStatus(FoodUser user,long chatId,LocalDate date,String text){this.user=user;this.chatId=chatId;this.localDate=date;this.desiredText=text;}
  public Long getId(){return id;} public long getChatId(){return chatId;} public LocalDate getLocalDate(){return localDate;} public String getDesiredText(){return desiredText;} public long getDesiredVersion(){return desiredVersion;} public long getDeliveredVersion(){return deliveredVersion;} public Long getTelegramMessageId(){return telegramMessageId;}
  public void request(LocalDate date,String text){localDate=date;desiredText=text;desiredVersion++;status=Status.PENDING;leaseToken=null;leaseExpiresAt=null;updatedAt=Instant.now();}
  public void claim(){status=Status.IN_PROGRESS;leaseToken=UUID.randomUUID();leaseExpiresAt=Instant.now().plusSeconds(60);}
  public UUID getLeaseToken(){return leaseToken;}
  public void delivered(long version,UUID token,Long messageId){if(token.equals(leaseToken)&&version==desiredVersion){deliveredVersion=version;telegramMessageId=messageId;status=Status.PENDING;leaseToken=null;leaseExpiresAt=null;updatedAt=Instant.now();}}
  public void rememberMessage(UUID token,Long messageId){if(token.equals(leaseToken)){telegramMessageId=messageId;updatedAt=Instant.now();}}
  public void retry(UUID token){if(token.equals(leaseToken)){status=Status.PENDING;leaseToken=null;leaseExpiresAt=null;}}
  public void clearTelegramMessage(){telegramMessageId=null;}
}
