package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

@Entity @Table(name="nutrition_source_cache") public class NutritionSourceCache {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @Column(nullable=false,unique=true) private String barcode; @Column(nullable=false) private String productName; private Integer caloriesPer100g; private BigDecimal proteinPer100g; private BigDecimal carbsPer100g; private BigDecimal fatPer100g; @Column(nullable=false,columnDefinition="text") private String sourceUrl; @Column(nullable=false) private Instant fetchedAt;
 protected NutritionSourceCache() {}
 public NutritionSourceCache(String barcode,String productName,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat,String sourceUrl,Instant fetchedAt){this.barcode=barcode;this.productName=productName;caloriesPer100g=calories;proteinPer100g=protein;carbsPer100g=carbs;fatPer100g=fat;this.sourceUrl=sourceUrl;this.fetchedAt=fetchedAt;}
 public String getBarcode(){return barcode;} public String getProductName(){return productName;} public Integer getCaloriesPer100g(){return caloriesPer100g;} public BigDecimal getProteinPer100g(){return proteinPer100g;} public BigDecimal getCarbsPer100g(){return carbsPer100g;} public BigDecimal getFatPer100g(){return fatPer100g;} public String getSourceUrl(){return sourceUrl;} public Instant getFetchedAt(){return fetchedAt;}
 public void refresh(String productName,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat,String sourceUrl,Instant fetchedAt){this.productName=productName;caloriesPer100g=calories;proteinPer100g=protein;carbsPer100g=carbs;fatPer100g=fat;this.sourceUrl=sourceUrl;this.fetchedAt=fetchedAt;}
}
