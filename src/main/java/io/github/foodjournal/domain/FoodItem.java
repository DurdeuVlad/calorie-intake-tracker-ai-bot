package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity @Table(name="food_items")
public class FoodItem {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @ManyToOne(optional=false) @JoinColumn(name="entry_id") private FoodEntry entry;
 @Column(nullable=false) private String name;
 private BigDecimal quantityGrams; private Integer calories; private BigDecimal proteinGrams; private BigDecimal carbsGrams; private BigDecimal fatGrams; @Column(nullable=false) private String nutritionSource="manual"; @Column(nullable=false) private String nutritionConfidence="unknown";
 protected FoodItem() {}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories){this.entry=entry;this.name=name;this.quantityGrams=quantityGrams;this.calories=calories;}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat){this(entry,name,quantityGrams,calories);proteinGrams=protein;carbsGrams=carbs;fatGrams=fat;}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat,String source,String confidence){this(entry,name,quantityGrams,calories,protein,carbs,fat);nutritionSource=source;nutritionConfidence=confidence;}
 public String getNutritionSource(){return nutritionSource;}
}
