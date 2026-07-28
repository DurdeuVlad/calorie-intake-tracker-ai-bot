package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramVoice(String file_id,String mime_type,Integer file_size) {}
