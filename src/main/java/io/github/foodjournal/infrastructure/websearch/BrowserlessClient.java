package io.github.foodjournal.infrastructure.websearch;

import io.github.foodjournal.config.BotProperties;
import java.util.Map;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Self-hosted Browserless page fetch, used when a search snippet does not contain a usable number. */
@Component public class BrowserlessClient {
 private static final int MAX_LENGTH=4000;
 private final RestClient client; private final boolean enabled; private final String token;
 @Autowired public BrowserlessClient(RestClient.Builder builder,BotProperties properties){this(properties.browserlessBaseUrl().isBlank()?null:builder.baseUrl(properties.browserlessBaseUrl()).build(),properties.browserlessToken());}
 BrowserlessClient(RestClient client,String token){this.client=client;this.enabled=client!=null;this.token=token==null?"":token;}
 public Optional<String> fetchText(String url){
  if(!enabled||url==null||url.isBlank())return Optional.empty();
  try{
   String html=client.post().uri(uri->uri.path("/content").queryParamIfPresent("token",token.isBlank()?Optional.empty():Optional.of(token)).build())
     .body(Map.of("url",url)).retrieve().body(String.class);
   String text=stripHtml(html);
   return text.isBlank()?Optional.empty():Optional.of(text.length()>MAX_LENGTH?text.substring(0,MAX_LENGTH):text);
  }catch(Exception ignored){return Optional.empty();}
 }
 private String stripHtml(String html){
  if(html==null)return "";
  String withoutScripts=html.replaceAll("(?is)<(script|style)[^>]*>.*?</\\1>","");
  String withoutTags=withoutScripts.replaceAll("(?s)<[^>]+>"," ");
  String unescaped=withoutTags.replace("&nbsp;"," ").replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").replace("&quot;","\"").replace("&#39;","'");
  return unescaped.replaceAll("\\s+"," ").trim();
 }
}
