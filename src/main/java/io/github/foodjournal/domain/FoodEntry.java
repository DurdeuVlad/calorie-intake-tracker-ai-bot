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
  public Long getId(){return id;} public Integer getCalories(){return calories;} public Instant getEatenAt(){return eatenAt;} public String getNutritionSource(){return nutritionSource;} public String getConfidence(){return confidence;}
  public String getOriginalMessage(){return originalMessage;} public FoodUser getUser(){return user;}
  public void revise(String message, Integer calories){if(message==null||message.isBlank()||calories==null||calories<0||calories>10000)throw new IllegalArgumentException("Invalid entry revision");this.originalMessage=message;this.calories=calories;}
  public void replaceEstimate(String message, Integer calories, String source, String confidence){revise(message,calories);nutritionSource=source;this.confidence=confidence;}
  public boolean isDeleted(){return deletedAt!=null;}
  public void markDeleted(Instant when){deletedAt=when==null?Instant.now():when;}
  public void restore(){deletedAt=null;}
}
