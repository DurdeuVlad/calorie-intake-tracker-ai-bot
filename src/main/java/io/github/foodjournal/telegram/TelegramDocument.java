package io.github.foodjournal.telegram;

public record TelegramDocument(String file_id, String file_name, String mime_type, Integer file_size) {}
