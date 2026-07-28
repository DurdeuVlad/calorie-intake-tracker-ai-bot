package io.github.foodjournal.application;

public interface FoodMediaExtractor {
  String extract(String telegramFileId, String mimeType, FoodMediaType type);
}
