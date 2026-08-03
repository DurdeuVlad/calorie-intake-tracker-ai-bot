package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity @Table(name="food_items")
public class FoodItem {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
 @ManyToOne(optional=false) @JoinColumn(name="entry_id") private FoodEntry entry;
 @Column(nullable=false) private String name;
 private BigDecimal quantityGrams;
 private BigDecimal quantity;
 @Column(nullable=false, length=16) private String quantityUnit="unspecified";
 private Integer calories; private BigDecimal proteinGrams; private BigDecimal carbsGrams; private BigDecimal fatGrams; @Column(nullable=false) private String nutritionSource="manual"; @Column(nullable=false) private String nutritionConfidence="unknown";
 protected FoodItem() {}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories){this(entry,name,quantityGrams,quantityGrams==null?QuantityUnit.UNSPECIFIED:QuantityUnit.G,calories,null,null,null,"manual","unknown");}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat){this(entry,name,quantityGrams,calories);proteinGrams=protein;carbsGrams=carbs;fatGrams=fat;}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantityGrams,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat,String source,String confidence){this(entry,name,quantityGrams,calories,protein,carbs,fat);nutritionSource=source;nutritionConfidence=confidence;}
 public FoodItem(FoodEntry entry,String name,BigDecimal quantity,QuantityUnit unit,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat,String source,String confidence){
  if(entry==null||name==null||name.isBlank()||unit==null)throw new IllegalArgumentException("Invalid food item");
  if(quantity!=null&&quantity.signum()<=0)throw new IllegalArgumentException("Quantity must be positive");
  this.entry=entry;this.name=name;this.quantity=quantity;this.quantityUnit=unit.databaseValue();this.quantityGrams=unit==QuantityUnit.G?quantity:null;this.calories=calories;
  proteinGrams=protein;carbsGrams=carbs;fatGrams=fat;nutritionSource=source==null?"manual":source;nutritionConfidence=confidence==null?"unknown":confidence;
 }
 public Long getId(){return id;} public FoodEntry getEntry(){return entry;} public String getName(){return name;}
 public BigDecimal getQuantity(){return quantity;} public QuantityUnit getQuantityUnit(){return QuantityUnit.fromDatabaseValue(quantityUnit);}
 /** Retained for callers and rows created before generic quantities were introduced. */
 public BigDecimal getQuantityGrams(){return quantityGrams;}
 public Integer getCalories(){return calories;} public BigDecimal getProteinGrams(){return proteinGrams;} public BigDecimal getCarbsGrams(){return carbsGrams;} public BigDecimal getFatGrams(){return fatGrams;}
 public String getNutritionSource(){return nutritionSource;} public String getNutritionConfidence(){return nutritionConfidence;}
 public void revise(String revisedName,Integer revisedCalories){if(revisedName==null||revisedName.isBlank()||revisedCalories==null||revisedCalories<0||revisedCalories>10000)throw new IllegalArgumentException("Invalid food item revision");name=revisedName;calories=revisedCalories;}
 public void reviseCalories(Integer revisedCalories){if(revisedCalories==null||revisedCalories<0||revisedCalories>10000)throw new IllegalArgumentException("Invalid food item calories");calories=revisedCalories;}
}
