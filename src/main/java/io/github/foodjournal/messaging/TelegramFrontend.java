package io.github.foodjournal.messaging;

import io.github.foodjournal.application.*;
import io.github.foodjournal.config.*;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Telegram HTTP details live here, outside the journal pipeline. */
@Component
@ConditionalOnProperty(prefix="food-journal.frontends.telegram", name="enabled", havingValue="true", matchIfMissing=true)
public class TelegramFrontend implements MessagingFrontend {
 private final RestClient api; private final BotProperties bot;
 public TelegramFrontend(RestClient.Builder builder,BotProperties bot){this.api=builder.baseUrl("https://api.telegram.org").build();this.bot=bot;}
 public String provider(){return "telegram";} public boolean enabled(){return !bot.telegramToken().isBlank();} public int messageLimit(){return 4096;}
 public String send(String conversationId,String text){Map<?,?> result=api.post().uri("/bot{token}/sendMessage",bot.telegramToken()).body(Map.of("chat_id",conversationId,"text",text)).retrieve().body(Map.class);Object row=result==null?null:result.get("result");Object id=row instanceof Map<?,?> map?map.get("message_id"):null;if(id==null)throw new IllegalStateException("Telegram delivery failed");return String.valueOf(id);}
 public void edit(String conversationId,String messageId,String text){api.post().uri("/bot{token}/editMessageText",bot.telegramToken()).body(Map.of("chat_id",conversationId,"message_id",messageId,"text",text)).retrieve().toBodilessEntity();}
 public TransientVoicePayload download(Attachment attachment){try{Map<?,?> response=api.get().uri(uri->uri.path("/bot/{token}/getFile").queryParam("file_id",attachment.handle()).build(bot.telegramToken())).retrieve().body(Map.class);Object result=response==null?null:response.get("result");Object path=result instanceof Map<?,?> map?map.get("file_path"):null;if(!(path instanceof String value)||value.isBlank())throw new IllegalStateException("media unavailable");String rawPath=value.startsWith("/")?value.substring(1):value;byte[] bytes=api.get().uri(java.net.URI.create("https://api.telegram.org/file/bot"+bot.telegramToken()+"/"+rawPath)).retrieve().body(byte[].class);if(bytes==null||bytes.length==0)throw new IllegalStateException("media unavailable");return new TransientVoicePayload(bytes);}catch(RuntimeException failure){throw new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Messaging media download failed",failure);}}
}
