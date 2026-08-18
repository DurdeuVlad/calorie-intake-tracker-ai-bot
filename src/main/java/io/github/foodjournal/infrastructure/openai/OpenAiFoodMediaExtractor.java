package io.github.foodjournal.infrastructure.openai;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;

@Component
public class OpenAiFoodMediaExtractor implements FoodMediaExtractor {
  private static final int MAX_MEDIA_BYTES=20_000_000;
  private final RestClient openai;
  private final BotProperties properties;

  @Autowired public OpenAiFoodMediaExtractor(RestClient.Builder builder,BotProperties properties){this(builder.baseUrl("https://api.openai.com/v1").build(),properties);}
  OpenAiFoodMediaExtractor(RestClient openai,BotProperties properties){this.openai=openai;this.properties=properties;}

  @Override public String extract(byte[] bytes,String mimeType,FoodMediaType type){
    if(properties.openaiApiKey()==null||properties.openaiApiKey().isBlank())throw failure(MediaProcessingException.Category.NOT_CONFIGURED,"OpenAI media extraction is not configured");
    String safeMime=supportedMimeType(mimeType,type);
    if(bytes==null||bytes.length==0||bytes.length>MAX_MEDIA_BYTES)throw failure(MediaProcessingException.Category.INVALID_MEDIA,"Media payload is invalid");
    String data="data:"+safeMime+";base64,"+Base64.getEncoder().encodeToString(bytes);
    Map<String,Object> mediaPart=type==FoodMediaType.PHOTO
        ?Map.of("type","input_image","image_url",data,"detail","auto")
        :Map.of("type","input_file","filename","document.pdf","file_data",data);
    Map<String,Object> body=Map.of("model",properties.openaiModel(),"input",List.of(Map.of("role","user","content",List.of(Map.of("type","input_text","text",prompt(type)),mediaPart))),"max_output_tokens",600);
    try{
      JsonNode response=openai.post().uri("/responses").header("Authorization","Bearer "+properties.openaiApiKey()).body(body).retrieve().body(JsonNode.class);
      return outputText(response);
    }catch(MediaProcessingException expected){throw expected;}
    catch(RestClientResponseException responseFailure){throw providerFailure(responseFailure);}
    catch(ResourceAccessException connectionFailure){throw failure(MediaProcessingException.Category.PROVIDER_TEMPORARY,"OpenAI media extraction is temporarily unavailable",connectionFailure);}
    catch(RuntimeException invalidResponse){throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI returned an invalid media extraction response",invalidResponse);}
  }

  private String supportedMimeType(String mimeType,FoodMediaType type){if(type==FoodMediaType.PHOTO&&(mimeType==null||mimeType.isBlank()))return "image/jpeg";if(type==FoodMediaType.PHOTO&&mimeType.startsWith("image/"))return mimeType;if(type==FoodMediaType.DOCUMENT&&"application/pdf".equals(mimeType))return mimeType;throw failure(MediaProcessingException.Category.INVALID_MEDIA,"Unsupported media type");}
  private String prompt(FoodMediaType type){return "Extract only food and nutrition-label evidence visible in this "+(type==FoodMediaType.PHOTO?"image":"PDF")+". State food names, portions, serving sizes, calories and macros only when legible. Do not invent missing values. Return a concise plain-text meal description suitable for a food journal.";}
  private String outputText(JsonNode response){if(response!=null)for(JsonNode output:response.path("output"))for(JsonNode content:output.path("content"))if("output_text".equals(content.path("type").asText())){String text=content.path("text").asText();if(!text.isBlank())return text.trim();}throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI returned no media extraction");}
  private MediaProcessingException providerFailure(RestClientResponseException failure){int status=failure.getStatusCode().value();if(status==401||status==403)return failure(MediaProcessingException.Category.NOT_CONFIGURED,"OpenAI media extraction is not configured",failure);if(status==404)return failure(MediaProcessingException.Category.MODEL_UNAVAILABLE,"OpenAI media model is unavailable",failure);if(status==429)return failure(MediaProcessingException.Category.RATE_LIMITED,"OpenAI is rate limited",failure);if(status>=500)return failure(MediaProcessingException.Category.PROVIDER_TEMPORARY,"OpenAI media extraction is temporarily unavailable",failure);return failure(MediaProcessingException.Category.PROVIDER_RESPONSE,"OpenAI rejected the media extraction request",failure);}
  private MediaProcessingException failure(MediaProcessingException.Category category,String message){return new MediaProcessingException(category,message);}
  private MediaProcessingException failure(MediaProcessingException.Category category,String message,Throwable cause){return new MediaProcessingException(category,message,cause);}
}
