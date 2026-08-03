package io.github.foodjournal.infrastructure.telegram;

import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;

@Component
public class TelegramHttpVoiceMediaClient implements TelegramVoiceMediaClient {
  private final RestClient telegram; private final BotProperties properties;
  @Autowired public TelegramHttpVoiceMediaClient(RestClient.Builder builder,BotProperties properties){this(builder.baseUrl("https://api.telegram.org").build(),properties);}
  TelegramHttpVoiceMediaClient(RestClient telegram,BotProperties properties){this.telegram=telegram;this.properties=properties;}
  @Override public TransientVoicePayload download(String telegramFileId){
    if(telegramFileId==null||telegramFileId.isBlank())throw new MediaProcessingException(MediaProcessingException.Category.INVALID_MEDIA,"Missing media file ID");
    try{Map<?,?> response=telegram.get().uri(uri->uri.path("/bot/{token}/getFile").queryParam("file_id",telegramFileId).build(properties.telegramToken())).retrieve().body(Map.class);Object result=response==null?null:response.get("result");if(!(result instanceof Map<?,?> file)||!(file.get("file_path") instanceof String path)||path.isBlank())throw new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Telegram media is unavailable");byte[] bytes=telegram.get().uri("/file/bot{token}/{path}",properties.telegramToken(),path).retrieve().body(byte[].class);if(bytes==null||bytes.length==0)throw new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Telegram media is unavailable");return new TransientVoicePayload(bytes);}catch(MediaProcessingException expected){throw expected;}catch(RestClientResponseException|ResourceAccessException failure){throw new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Telegram media download failed",failure);}
  }
}
