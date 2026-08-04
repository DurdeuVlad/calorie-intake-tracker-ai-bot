package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.domain.FoodUser;
import io.github.foodjournal.infrastructure.websearch.BrowserlessClient;
import io.github.foodjournal.infrastructure.websearch.SearxngClient;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;

class JournalToolExecutorWebSearchTest {
  private final FoodUser user=new FoodUser(1,"Vlad");
  private JournalToolExecutor executor(SearxngClient searxng,BrowserlessClient browserless){return new JournalToolExecutor(new ObjectMapper(),null,null,null,null,null,null,null,null,null,null,null,null,searxng,browserless);}
  private AgentToolResult execute(JournalToolExecutor executor,String name,String arguments){return executor.execute(new AgentContext(user,1,true,"test",Instant.now()),new JournalAgentModel.ToolCall("call",name,arguments),new ArrayList<>());}

  @Test void searchWebFailsWhenUnconfigured(){AgentToolResult result=execute(executor(null,null),"search_web","{\"query\":\"taco bell burrito calories\"}");assertThat(result.ok()).isFalse();assertThat(result.code()).isEqualTo("TEMPORARY_FAILURE");}
  @Test void searchWebRequiresAQuery(){SearxngClient searxng=mock(SearxngClient.class);AgentToolResult result=execute(executor(searxng,null),"search_web","{}");assertThat(result.code()).isEqualTo("VALIDATION_ERROR");verifyNoInteractions(searxng);}
  @Test void searchWebReturnsRankedResults(){SearxngClient searxng=mock(SearxngClient.class);when(searxng.search("taco bell burrito calories")).thenReturn(List.of(new SearxngClient.WebSearchResult("Burrito Supreme Nutrition","https://tacobell.com/menu/burrito","710 calories")));AgentToolResult result=execute(executor(searxng,null),"search_web","{\"query\":\"taco bell burrito calories\"}");assertThat(result.ok()).isTrue();@SuppressWarnings("unchecked") List<Map<String,Object>> results=(List<Map<String,Object>>)result.data().get("results");assertThat(results).hasSize(1);assertThat(results.getFirst()).containsEntry("url","https://tacobell.com/menu/burrito");}
  @Test void searchWebReportsNoResults(){SearxngClient searxng=mock(SearxngClient.class);when(searxng.search(anyString())).thenReturn(List.of());AgentToolResult result=execute(executor(searxng,null),"search_web","{\"query\":\"an unknown dish\"}");assertThat(result.code()).isEqualTo("NOT_FOUND");}

  @Test void fetchWebPageFailsWhenUnconfigured(){AgentToolResult result=execute(executor(null,null),"fetch_web_page","{\"url\":\"https://tacobell.com/menu/burrito\"}");assertThat(result.code()).isEqualTo("TEMPORARY_FAILURE");}
  @Test void fetchWebPageRejectsNonHttpSchemes(){BrowserlessClient browserless=mock(BrowserlessClient.class);AgentToolResult result=execute(executor(null,browserless),"fetch_web_page","{\"url\":\"file:///etc/passwd\"}");assertThat(result.code()).isEqualTo("VALIDATION_ERROR");verifyNoInteractions(browserless);}
  @Test void fetchWebPageBlocksLoopbackAndPrivateHosts(){BrowserlessClient browserless=mock(BrowserlessClient.class);for(String url:List.of("http://localhost:8080/","http://127.0.0.1/","http://10.0.0.5/","http://192.168.1.1/","http://169.254.169.254/latest/meta-data")){AgentToolResult result=execute(executor(null,browserless),"fetch_web_page","{\"url\":\""+url+"\"}");assertThat(result.code()).as(url).isEqualTo("VALIDATION_ERROR");}verifyNoInteractions(browserless);}
  @Test void fetchWebPageReturnsExtractedText(){BrowserlessClient browserless=mock(BrowserlessClient.class);when(browserless.fetchText("https://tacobell.com/menu/burrito")).thenReturn(Optional.of("Burrito Supreme: 710 calories"));AgentToolResult result=execute(executor(null,browserless),"fetch_web_page","{\"url\":\"https://tacobell.com/menu/burrito\"}");assertThat(result.ok()).isTrue();assertThat(result.data().get("text")).isEqualTo("Burrito Supreme: 710 calories");}
  @Test void fetchWebPageReportsWhenPageCannotBeFetched(){BrowserlessClient browserless=mock(BrowserlessClient.class);when(browserless.fetchText(anyString())).thenReturn(Optional.empty());AgentToolResult result=execute(executor(null,browserless),"fetch_web_page","{\"url\":\"https://tacobell.com/menu/burrito\"}");assertThat(result.code()).isEqualTo("NOT_FOUND");}
}
