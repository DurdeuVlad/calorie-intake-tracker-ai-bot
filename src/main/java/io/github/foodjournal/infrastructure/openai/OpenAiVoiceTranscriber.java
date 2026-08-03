package io.github.foodjournal.infrastructure.openai;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.util.*;
import org.springframework.web.client.*;

@Component
public class OpenAiVoiceTranscriber implements VoiceTranscriber {
  private static final int MAX_VOICE_BYTES=20_000_000;
  private final RestClient openai;private final BotProperties properties;private final TelegramVoiceMediaClient media;
  @Autowired public OpenAiVoiceTranscriber(RestClient.Builder builder,BotProperties properties,TelegramVoiceMediaClient media){this(builder.baseUrl("https://api.openai.com/v1").build(),properties,media);}
  OpenAiVoiceTranscriber(RestClient openai,BotProperties properties){this(openai,properties,null);}
  OpenAiVoiceTranscriber(RestClient openai,BotProperties properties,TelegramVoiceMediaClient media){this.openai=openai;this.properties=properties;this.media=media;}
  @Override public String transcribe(String telegramFileId,String mimeType){if(media==null)throw failure(MediaProcessingException.Category.NOT_CONFIGURED,"Telegram media download is not configured");try(TransientVoicePayload payload=media.download(telegramFileId)){return transcribe(payload.bytes(),mimeType);}catch(MediaProcessingException expected){throw expected;}catch(RuntimeException failure){throw failure(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Telegram media download failed",failure);}}
  public String transcribe(byte[] bytes,String mimeType){
    if(properties.openaiApiKey()==null||properties.openaiApiKey().isBlank())throw failure(MediaProcessingException.Category.NOT_CONFIGURED,"OpenAI transcription is not configured");
    if(bytes==null||bytes.length==0||bytes.length>MAX_VOICE_BYTES)throw failure(MediaProcessingException.Category.INVALID_MEDIA,"Voice note is invalid");
    MultiValueMap<String,Object> form=new LinkedMultiValueMap<>();form.add("model",properties.openaiTranscriptionModel());HttpHeaders headers=new HttpHeaders();headers.setContentType(mediaType(mimeType));form.add("file",new HttpEntity<>(new ByteArrayResource(bytes){@Override public String getFilename(){return "voice.ogg";}},headers));
    try{JsonNode response=openai.post().uri("/audio/transcriptions").header("Authorization","Bearer "+properties.openaiApiKey()).contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve().body(JsonNode.class);String text=response==null?null:response.path("text").asText(null);if(text==null||text.isBlank())throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI returned no transcript");return text.trim();}catch(MediaProcessingException expected){throw expected;}catch(RestClientResponseException responseFailure){throw providerFailure(responseFailure);}catch(ResourceAccessException connectionFailure){throw failure(MediaProcessingException.Category.PROVIDER_TEMPORARY,"OpenAI is temporarily unavailable",connectionFailure);}catch(RuntimeException invalidResponse){throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI returned an invalid transcription response",invalidResponse);}
  }
  private MediaType mediaType(String value){try{return value==null||value.isBlank()?MediaType.valueOf("audio/ogg"):MediaType.valueOf(value);}catch(IllegalArgumentException ignored){return MediaType.APPLICATION_OCTET_STREAM;}}
  private MediaProcessingException providerFailure(RestClientResponseException failure){int status=failure.getStatusCode().value();if(status==401||status==403)return failure(MediaProcessingException.Category.NOT_CONFIGURED,"OpenAI transcription is not configured",failure);if(status==404)return failure(MediaProcessingException.Category.MODEL_UNAVAILABLE,"OpenAI transcription model is unavailable",failure);if(status==429)return failure(MediaProcessingException.Category.RATE_LIMITED,"OpenAI is rate limited",failure);if(status>=500)return failure(MediaProcessingException.Category.PROVIDER_TEMPORARY,"OpenAI is temporarily unavailable",failure);return failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI rejected the transcription request",failure);}
  private MediaProcessingException failure(MediaProcessingException.Category category,String message){return new MediaProcessingException(category,message);}private MediaProcessingException failure(MediaProcessingException.Category category,String message,Throwable cause){return new MediaProcessingException(category,message,cause);}
}
