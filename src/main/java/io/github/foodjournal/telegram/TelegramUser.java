package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramUser(Long id, String first_name, String language_code) { public TelegramUser(Long id,String firstName){this(id,firstName,null);} }
