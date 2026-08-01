package io.github.foodjournal.domain;

import jakarta.persistence.*;

@Entity @Table(name="messaging_identities", uniqueConstraints=@UniqueConstraint(columnNames={"provider","external_user_id"}))
public class MessagingIdentity {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false,length=32) private String provider;
 @Column(name="external_user_id",nullable=false) private String externalUserId;
 protected MessagingIdentity(){}
 public MessagingIdentity(FoodUser user,String provider,String externalUserId){this.user=user;this.provider=provider;this.externalUserId=externalUserId;}
 public FoodUser getUser(){return user;} public String getProvider(){return provider;} public String getExternalUserId(){return externalUserId;}
}
