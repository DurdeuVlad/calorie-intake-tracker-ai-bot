package io.github.foodjournal.application;

import io.github.foodjournal.domain.FoodUser;

public interface NutritionResolver {
  ResolvedMealItem resolve(FoodUser user, JournalIntent.MealItem item);
  record ResolvedMealItem(JournalIntent.MealItem item, String source) {}
  static NutritionResolver noop(){return (user,item)->new ResolvedMealItem(item,"manual");}
}
