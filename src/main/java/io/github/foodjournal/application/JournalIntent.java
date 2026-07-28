package io.github.foodjournal.application;
import java.time.Instant; import java.util.List;
public record JournalIntent(IntentType type, String mealDescription, Integer calories, String query, Long entryId, String timezone, Integer calorieTarget, Boolean reportsEnabled, List<MealItem> items, Instant eatenAt, String nutritionSource, String confidence) {
 public JournalIntent(IntentType type,String mealDescription,Integer calories,String query,Long entryId,String timezone,Integer calorieTarget,Boolean reportsEnabled,List<MealItem> items){this(type,mealDescription,calories,query,entryId,timezone,calorieTarget,reportsEnabled,items,null,null,null);}
 public record MealItem(String name, Double grams, Integer calories, Double proteinGrams, Double carbsGrams, Double fatGrams) { public MealItem(String name,Double grams,Integer calories){this(name,grams,calories,null,null,null);} }
}
