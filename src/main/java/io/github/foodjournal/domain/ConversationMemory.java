package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity @Table(name="conversation_memory")
public class ConversationMemory {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false,length=16) private String role;
 @Column(nullable=false,columnDefinition="text") private String content;
 @Column(nullable=false) private Instant createdAt=Instant.now();
 protected ConversationMemory(){}
 public ConversationMemory(FoodUser user,String role,String content){this.user=user;this.role=role;this.content=content;}
 public String getRole(){return role;} public String getContent(){return content;} public Instant getCreatedAt(){return createdAt;}
}
