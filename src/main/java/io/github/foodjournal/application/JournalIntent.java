package io.github.foodjournal.application;
import java.util.List;
public record JournalIntent(IntentType type, String mealDescription, Integer calories, String query, Long entryId, String timezone, Integer calorieTarget, List<MealItem> items) { public record MealItem(String name, Double grams, Integer calories) {} }
