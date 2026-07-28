package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;
@JsonIgnoreProperties(ignoreUnknown=true) public record TelegramMessage(Long message_id, TelegramChat chat, TelegramUser from, String text, TelegramVoice voice, List<TelegramPhoto> photo, TelegramDocument document, String caption) {
 public TelegramMessage(Long message_id, TelegramChat chat, TelegramUser from, String text, TelegramVoice voice, List<TelegramPhoto> photo, TelegramDocument document){this(message_id,chat,from,text,voice,photo,document,null);}
}
