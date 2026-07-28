package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramUpdate(Long update_id, TelegramMessage message, TelegramMessage edited_message) {}
