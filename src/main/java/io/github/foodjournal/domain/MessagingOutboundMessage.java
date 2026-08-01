package io.github.foodjournal.domain;

import jakarta.persistence.*; import java.time.*; import java.util.UUID;
@Entity @Table(name="messaging_outbox") public class MessagingOutboundMessage {
 public enum Status { PENDING, IN_PROGRESS, SENT }
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id; @Column(nullable=false,length=32) private String provider; @Column(name="conversation_id",nullable=false) private String conversationId; @Column(nullable=false,columnDefinition="text") private String text; @Enumerated(EnumType.STRING) @Column(nullable=false) private Status status=Status.PENDING; private int attempts; private Instant nextAttemptAt=Instant.now(); private Instant leaseExpiresAt; private UUID leaseToken;
 protected MessagingOutboundMessage(){} public MessagingOutboundMessage(String provider,String conversationId,String text){this.provider=provider;this.conversationId=conversationId;this.text=text;}
 public Long getId(){return id;} public String getProvider(){return provider;} public String getConversationId(){return conversationId;} public String getText(){return text;} public Status getStatus(){return status;} public UUID getLeaseToken(){return leaseToken;}
 public void claim(){status=Status.IN_PROGRESS;leaseToken=UUID.randomUUID();leaseExpiresAt=Instant.now().plusSeconds(60);} public void sent(){status=Status.SENT;leaseToken=null;leaseExpiresAt=null;} public void retry(){status=Status.PENDING;attempts++;nextAttemptAt=Instant.now().plusSeconds(Math.min(300,1L<<Math.min(attempts,8)));leaseToken=null;leaseExpiresAt=null;}
}
