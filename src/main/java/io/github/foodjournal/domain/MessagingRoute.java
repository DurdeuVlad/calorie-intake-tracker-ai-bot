package io.github.foodjournal.domain;

import jakarta.persistence.*;

@Entity @Table(name="messaging_routes", uniqueConstraints=@UniqueConstraint(columnNames={"user_id","provider","conversation_id"}))
public class MessagingRoute {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false,length=32) private String provider;
 @Column(name="conversation_id",nullable=false) private String conversationId;
 protected MessagingRoute(){}
 public MessagingRoute(FoodUser user,String provider,String conversationId){this.user=user;this.provider=provider;this.conversationId=conversationId;}
 public FoodUser getUser(){return user;} public String getProvider(){return provider;} public String getConversationId(){return conversationId;}
}
