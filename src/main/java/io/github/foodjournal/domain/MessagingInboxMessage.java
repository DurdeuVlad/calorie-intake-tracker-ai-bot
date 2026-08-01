package io.github.foodjournal.domain;

import jakarta.persistence.*; import java.time.*; import java.util.UUID;

@Entity @Table(name="messaging_inbox", uniqueConstraints=@UniqueConstraint(columnNames={"provider","event_id"})) public class MessagingInboxMessage {
 public enum Status { PENDING, IN_PROGRESS, COMPLETED, FAILED }
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id; @Column(nullable=false,length=32) private String provider; @Column(name="event_id",nullable=false) private String eventId;
 @Column(nullable=false,columnDefinition="text") private String payload; @Enumerated(EnumType.STRING) @Column(nullable=false) private Status status=Status.PENDING; private int attempts; private Instant nextAttemptAt=Instant.now(); private Instant leaseExpiresAt; private UUID leaseToken;
 protected MessagingInboxMessage(){} public MessagingInboxMessage(String provider,String eventId,String payload){this.provider=provider;this.eventId=eventId;this.payload=payload;}
 public Long getId(){return id;} public String getPayload(){return payload;} public Status getStatus(){return status;} public UUID getLeaseToken(){return leaseToken;}
 public void claim(){status=Status.IN_PROGRESS;leaseToken=UUID.randomUUID();leaseExpiresAt=Instant.now().plusSeconds(60);} public void complete(UUID token){if(token.equals(leaseToken)){status=Status.COMPLETED;payload="";leaseToken=null;leaseExpiresAt=null;}}
 public void retry(UUID token){if(token.equals(leaseToken)){attempts++;if(attempts>=3){status=Status.FAILED;payload="";}else{status=Status.PENDING;nextAttemptAt=Instant.now().plusSeconds(Math.min(300,1L<<attempts));}leaseToken=null;leaseExpiresAt=null;}}
}
