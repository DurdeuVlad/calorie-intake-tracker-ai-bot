package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;

@Entity @Table(name="pending_food_drafts")
public class PendingFoodDraft {
 @Id private Long userId;
 @OneToOne @MapsId @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false,columnDefinition="text") private String rawMessage;
 @Column(nullable=false) private Instant createdAt;
 @Column(nullable=false) private Instant expiresAt;
 protected PendingFoodDraft(){}
 public PendingFoodDraft(FoodUser user,String raw,Instant now){this.user=user;rawMessage=raw;createdAt=now;expiresAt=now.plus(Duration.ofMinutes(30));}
 public String getRawMessage(){return rawMessage;} public Instant getExpiresAt(){return expiresAt;}
 public void replace(String raw,Instant now){rawMessage=raw;createdAt=now;expiresAt=now.plus(Duration.ofMinutes(30));}
}
