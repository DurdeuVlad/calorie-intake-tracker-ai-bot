package io.github.foodjournal.application;

public interface FoodMediaExtractor {
  String extract(String telegramFileId, String mimeType, FoodMediaType type);
  default String extract(byte[] bytes, String mimeType, FoodMediaType type) { throw new UnsupportedOperationException("Portable media extraction is unavailable"); }
}
