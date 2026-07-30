package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.*;
import java.util.UUID;

/** Server-owned nutrition evidence. Tool callers can only reference its UUID. */
@Entity @Table(name="pending_nutrition_quotes")
public class PendingNutritionQuote {
  public enum Type { PACKAGED_MATCH, AI_ESTIMATE }
  @Id @Column(name="quote_id", nullable=false, updatable=false) private UUID id;
  @Column(name="batch_id", nullable=false, updatable=false) private UUID batchId;
  @ManyToOne(optional=false, fetch=FetchType.LAZY) @JoinColumn(name="user_id", nullable=false) private FoodUser user;
  @Enumerated(EnumType.STRING) @Column(name="quote_type", nullable=false, length=32) private Type type;
  @Column(name="product_name", nullable=false) private String productName;
  private String brand;
  @Column(nullable=false, precision=10, scale=2) private BigDecimal grams;
  @Column(name="calories_per_100g", nullable=false) private Integer caloriesPer100g;
  private String barcode;
  @Column(name="source_url", columnDefinition="text") private String sourceUrl;
  @Column(name="estimate_basis", length=512) private String estimateBasis;
  @Column(name="created_at", nullable=false) private Instant createdAt;
  @Column(name="expires_at", nullable=false) private Instant expiresAt;
  protected PendingNutritionQuote() {}
  private PendingNutritionQuote(FoodUser user, UUID batchId, Type type, String name, String brand, double grams, int calories, String barcode, String sourceUrl, String basis, Instant now) {
    this.id=UUID.randomUUID(); this.batchId=batchId; this.user=user; this.type=type; this.productName=name; this.brand=brand;
    this.grams=BigDecimal.valueOf(grams); this.caloriesPer100g=calories; this.barcode=barcode; this.sourceUrl=sourceUrl;
    this.estimateBasis=basis; this.createdAt=now; this.expiresAt=now.plus(Duration.ofMinutes(30));
  }
  public static PendingNutritionQuote packaged(FoodUser user, UUID batchId, String name, String brand, double grams, int calories, String barcode, String sourceUrl, Instant now) { return new PendingNutritionQuote(user,batchId,Type.PACKAGED_MATCH,name,brand,grams,calories,barcode,sourceUrl,null,now); }
  public static PendingNutritionQuote estimate(FoodUser user, String name, double grams, int calories, String basis, Instant now) { return new PendingNutritionQuote(user,UUID.randomUUID(),Type.AI_ESTIMATE,name,null,grams,calories,null,null,basis,now); }
  public UUID getId(){return id;} public UUID getBatchId(){return batchId;} public FoodUser getUser(){return user;} public Type getType(){return type;} public String getProductName(){return productName;} public String getBrand(){return brand;} public double getGrams(){return grams.doubleValue();} public int getCaloriesPer100g(){return caloriesPer100g;} public String getBarcode(){return barcode;} public String getSourceUrl(){return sourceUrl;} public String getEstimateBasis(){return estimateBasis;} public Instant getCreatedAt(){return createdAt;} public Instant getExpiresAt(){return expiresAt;}
}
