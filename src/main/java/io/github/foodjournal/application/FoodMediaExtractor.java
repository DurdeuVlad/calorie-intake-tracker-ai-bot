package io.github.foodjournal.application;

public interface FoodMediaExtractor {
  String extract(byte[] bytes, String mimeType, FoodMediaType type);
}
