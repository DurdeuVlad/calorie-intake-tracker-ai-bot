package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramUser(Long id, String first_name) {}
