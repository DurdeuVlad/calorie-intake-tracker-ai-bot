package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;

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
  protected PinnedDailyStatus() {}
  public PinnedDailyStatus(FoodUser user,long chatId,LocalDate date,String text){this.user=user;this.chatId=chatId;this.localDate=date;this.desiredText=text;}
  public Long getId(){return id;} public long getChatId(){return chatId;} public LocalDate getLocalDate(){return localDate;} public String getDesiredText(){return desiredText;} public long getDesiredVersion(){return desiredVersion;} public long getDeliveredVersion(){return deliveredVersion;} public Long getTelegramMessageId(){return telegramMessageId;}
  public void request(LocalDate date,String text){localDate=date;desiredText=text;desiredVersion++;updatedAt=Instant.now();}
  public void delivered(long version,Long messageId){if(version==desiredVersion){deliveredVersion=version;telegramMessageId=messageId;updatedAt=Instant.now();}}
  public void clearTelegramMessage(){telegramMessageId=null;}
}
