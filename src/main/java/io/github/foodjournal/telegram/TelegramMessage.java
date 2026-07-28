package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramMessage(Long message_id, TelegramChat chat, TelegramUser from, String text, TelegramVoice voice, Object photo, Object document) {}
