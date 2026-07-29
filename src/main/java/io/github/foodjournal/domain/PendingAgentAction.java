package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;

@Entity @Table(name="pending_agent_actions")
public class PendingAgentAction {
 @Id private Long userId;
 @OneToOne @MapsId @JoinColumn(name="user_id") private FoodUser user;
 @Column(nullable=false) private String actionType;
 @Column(nullable=false) private Long entryId;
 @Column(columnDefinition="text") private String description;
 private Integer calories;
 @Column(nullable=false,columnDefinition="text") private String summary;
 @Column(nullable=false) private Instant createdAt;
 @Column(nullable=false) private Instant expiresAt;
 protected PendingAgentAction(){}
 public static PendingAgentAction forAction(FoodUser user,String action,Long entryId,String description,Integer calories,Instant now){PendingAgentAction p=new PendingAgentAction();p.user=user;p.actionType=action;p.entryId=entryId;p.description=description;p.calories=calories;p.summary=action+" entry #"+entryId;p.createdAt=now;p.expiresAt=now.plus(Duration.ofMinutes(30));return p;}
 public void replace(String action,Long entry,String text,Integer kcal,Instant now){actionType=action;entryId=entry;description=text;calories=kcal;summary=action+" entry #"+entry;createdAt=now;expiresAt=now.plus(Duration.ofMinutes(30));}
 public String getActionType(){return actionType;} public Long getEntryId(){return entryId;} public String getDescription(){return description;} public Integer getCalories(){return calories;} public String getSummary(){return summary;} public Instant getExpiresAt(){return expiresAt;} public Instant getCreatedAt(){return createdAt;}
}
