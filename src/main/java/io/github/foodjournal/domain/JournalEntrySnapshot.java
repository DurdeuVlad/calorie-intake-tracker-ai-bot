package io.github.foodjournal.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/** Immutable journal state stored before or after one mutation. */
public record JournalEntrySnapshot(Long entryId, String originalMessage, Instant eatenAt, Integer calories,
    String nutritionSource, String confidence, Instant deletedAt, List<FoodItemSnapshot> items) {
  public JournalEntrySnapshot {
    items=items==null?List.of():List.copyOf(items);
  }

  public static JournalEntrySnapshot capture(FoodEntry entry,List<FoodItem> items){
    if(entry==null)throw new IllegalArgumentException("Entry is required");
    List<FoodItemSnapshot> snapshots=items==null?List.of():items.stream().map(FoodItemSnapshot::capture).toList();
    return new JournalEntrySnapshot(entry.getId(),entry.getOriginalMessage(),entry.getEatenAt(),entry.getCalories(),
        entry.getNutritionSource(),entry.getConfidence(),entry.getDeletedAt(),snapshots);
  }

  public record FoodItemSnapshot(Long itemId,String name,BigDecimal quantity,QuantityUnit quantityUnit,
      BigDecimal quantityGrams,Integer calories,BigDecimal proteinGrams,BigDecimal carbsGrams,BigDecimal fatGrams,
      String nutritionSource,String nutritionConfidence){
    static FoodItemSnapshot capture(FoodItem item){
      return new FoodItemSnapshot(item.getId(),item.getName(),item.getQuantity(),item.getQuantityUnit(),item.getQuantityGrams(),
          item.getCalories(),item.getProteinGrams(),item.getCarbsGrams(),item.getFatGrams(),item.getNutritionSource(),item.getNutritionConfidence());
    }
    public FoodItem recreateFor(FoodEntry entry){
      BigDecimal effectiveQuantity=quantity!=null?quantity:quantityGrams;
      QuantityUnit effectiveUnit=quantityUnit!=null?quantityUnit:(quantityGrams==null?QuantityUnit.UNSPECIFIED:QuantityUnit.G);
      return new FoodItem(entry,name,effectiveQuantity,effectiveUnit,calories,proteinGrams,carbsGrams,fatGrams,nutritionSource,nutritionConfidence);
    }
  }
}
