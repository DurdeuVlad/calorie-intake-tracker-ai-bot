package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramChat(Long id) {}
