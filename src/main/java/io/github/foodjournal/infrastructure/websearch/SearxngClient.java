package io.github.foodjournal.infrastructure.websearch;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.config.BotProperties;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Self-hosted SearxNG search, used to find nutrition facts Open Food Facts does not carry (restaurant/menu items). */
@Component public class SearxngClient {
 private final RestClient client; private final boolean enabled;
 @Autowired public SearxngClient(RestClient.Builder builder,BotProperties properties){this(properties.searxngBaseUrl().isBlank()?null:builder.baseUrl(properties.searxngBaseUrl()).build());}
 SearxngClient(RestClient client){this.client=client;this.enabled=client!=null;}
 public List<WebSearchResult> search(String query){
  if(!enabled||query==null||query.isBlank())return List.of();
  try{
   JsonNode response=client.get().uri(uri->uri.path("/search").queryParam("q",query).queryParam("format","json").build()).retrieve().body(JsonNode.class);
   JsonNode results=response==null?null:response.path("results");
   if(results==null||!results.isArray())return List.of();
   List<WebSearchResult> mapped=new ArrayList<>();
   for(JsonNode result:results){
    String title=result.path("title").asText("");String url=result.path("url").asText("");String snippet=result.path("content").asText("");
    if(title.isBlank()||url.isBlank())continue;
    mapped.add(new WebSearchResult(title,url,snippet));
    if(mapped.size()>=5)break;
   }
   return List.copyOf(mapped);
  }catch(Exception ignored){return List.of();}
 }
 public record WebSearchResult(String title,String url,String snippet) {}
}
