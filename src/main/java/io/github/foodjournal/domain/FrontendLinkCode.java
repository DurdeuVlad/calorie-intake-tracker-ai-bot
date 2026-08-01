package io.github.foodjournal.domain;

import jakarta.persistence.*; import java.time.*;

@Entity @Table(name="frontend_link_codes") public class FrontendLinkCode {
 @Id private String code; @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false) private Instant expiresAt; private Instant consumedAt;
 protected FrontendLinkCode(){} public FrontendLinkCode(String code,FoodUser user,Instant expiresAt){this.code=code;this.user=user;this.expiresAt=expiresAt;}
 public FoodUser getUser(){return user;} public boolean redeemable(Instant now){return consumedAt==null&&expiresAt.isAfter(now);} public void consume(){consumedAt=Instant.now();}
}
