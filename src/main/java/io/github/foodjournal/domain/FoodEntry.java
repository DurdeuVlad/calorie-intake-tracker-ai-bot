package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity @Table(name="food_entries")
public class FoodEntry {
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
  @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
  @Column(nullable=false, columnDefinition="text") private String originalMessage;
  @Column(nullable=false) private Instant eatenAt;
  private Integer calories;
  @Column(nullable=false) private String nutritionSource="manual";
  @Column(nullable=false) private String confidence="unknown";
  @Column(nullable=false) private Instant createdAt=Instant.now();
  private Instant deletedAt;
  protected FoodEntry() {}
  public FoodEntry(FoodUser user,String originalMessage,Instant eatenAt,Integer calories,String source,String confidence){this.user=user;this.originalMessage=originalMessage;this.eatenAt=eatenAt;this.calories=calories;this.nutritionSource=source;this.confidence=confidence;}
  public Long getId(){return id;} public Integer getCalories(){return calories;} public Instant getEatenAt(){return eatenAt;} public String getNutritionSource(){return nutritionSource;} public String getConfidence(){return confidence;} public Instant getDeletedAt(){return deletedAt;}
  public String getOriginalMessage(){return originalMessage;} public FoodUser getUser(){return user;}
  public void revise(String message, Integer calories){if(message==null||message.isBlank()||calories==null||calories<0||calories>10000)throw new IllegalArgumentException("Invalid entry revision");this.originalMessage=message;this.calories=calories;}
  public void moveTo(Instant when){if(when==null||when.isAfter(Instant.now()))throw new IllegalArgumentException("Invalid meal time");this.eatenAt=when;}
  public void replaceEstimate(String message, Integer calories, String source, String confidence){revise(message,calories);nutritionSource=source;this.confidence=confidence;}
  /** Restores all mutable entry fields from a persisted undo snapshot. Item rows are restored separately. */
  public void restoreFrom(JournalEntrySnapshot snapshot){
    if(snapshot==null||snapshot.entryId()==null||id==null||!id.equals(snapshot.entryId()))throw new IllegalArgumentException("Snapshot belongs to another entry");
    if(snapshot.originalMessage()==null||snapshot.originalMessage().isBlank()||snapshot.eatenAt()==null)throw new IllegalArgumentException("Invalid entry snapshot");
    originalMessage=snapshot.originalMessage();eatenAt=snapshot.eatenAt();calories=snapshot.calories();nutritionSource=snapshot.nutritionSource();confidence=snapshot.confidence();deletedAt=snapshot.deletedAt();
  }
  public boolean isDeleted(){return deletedAt!=null;}
  public void markDeleted(Instant when){deletedAt=when==null?Instant.now():when;}
  public void restore(){deletedAt=null;}
}
