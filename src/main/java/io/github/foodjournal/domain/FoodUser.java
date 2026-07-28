package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity @Table(name = "food_users")
public class FoodUser {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @Column(name="telegram_user_id", nullable=false, unique=true) private long telegramUserId;
  @Column(name="display_name") private String displayName;
  @Column(nullable=false) private Instant createdAt = Instant.now();
  protected FoodUser() {}
  public FoodUser(long telegramUserId, String displayName) { this.telegramUserId=telegramUserId; this.displayName=displayName; }
  public Long getId(){return id;} public long getTelegramUserId(){return telegramUserId;}
}
