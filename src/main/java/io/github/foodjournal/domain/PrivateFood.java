package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

@Entity @Table(name="private_foods",uniqueConstraints=@UniqueConstraint(columnNames={"user_id","name"})) public class PrivateFood {
 @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id; @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user; @Column(nullable=false) private String name; private Integer caloriesPer100g; private BigDecimal proteinPer100g; private BigDecimal carbsPer100g; private BigDecimal fatPer100g; @Column(nullable=false) private Instant createdAt=Instant.now();
 protected PrivateFood() {}
 public PrivateFood(FoodUser user,String name,Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat){this.user=user;this.name=name;caloriesPer100g=calories;proteinPer100g=protein;carbsPer100g=carbs;fatPer100g=fat;}
 public String getName(){return name;} public Integer getCaloriesPer100g(){return caloriesPer100g;} public BigDecimal getProteinPer100g(){return proteinPer100g;} public BigDecimal getCarbsPer100g(){return carbsPer100g;} public BigDecimal getFatPer100g(){return fatPer100g;}
 public void refresh(Integer calories,BigDecimal protein,BigDecimal carbs,BigDecimal fat){caloriesPer100g=calories;proteinPer100g=protein;carbsPer100g=carbs;fatPer100g=fat;}
}
