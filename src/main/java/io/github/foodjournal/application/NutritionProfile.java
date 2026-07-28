package io.github.foodjournal.application;

public record NutritionProfile(String name, Integer caloriesPer100g, Double proteinPer100g, Double carbsPer100g, Double fatPer100g, String source, String sourceUrl) {}
