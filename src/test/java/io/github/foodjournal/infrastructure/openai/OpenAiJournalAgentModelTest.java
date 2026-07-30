package io.github.foodjournal.infrastructure.openai;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.application.AgentContext;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.MockRestServiceServer;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
import org.springframework.http.MediaType;

class OpenAiJournalAgentModelTest {
  private final OpenAiJournalAgentModel model = new OpenAiJournalAgentModel(RestClient.builder(), new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","key","test"), new ObjectMapper());

  @Test void dailyTotalPromptRoutesRomanianAndEnglishToTodaySummary() {
    String prompt = model.instructions(true);
    assertThat(prompt).contains("cate calorii azi?", "how many calories today?", "always call get_today_summary", "Never call search_entries for a daily-total question");
  }

  @Test void helpfulPromptUsesContextAndNutritionBeforeAskingForMoreWork() {
    String prompt = model.instructions(true);
    assertThat(prompt).contains("Reduce the user's effort", "same as before",
        "get_private_food, resolve_nutrition, lookup_food", "one concrete, low-effort question",
        "66 kcal x 4.5", "297 kcal", "banana");
  }

  @Test void correctionPromptNeverTreatsOnlyOnceAsANewMeal() {
    assertThat(model.instructions(true)).contains("noteaza doar o data", "correction request", "Never call create_food_entry", "prepare_entry_delete");
  }

  @Test void promptRequiresPlainSelfContainedTelegramReplies() {
    assertThat(model.instructions(true)).contains("Telegram is plain text", "never use Markdown or HTML", "do not append generic offers");
  }

  @Test void toolDefinitionsExposeTypedArgumentsForSensorsAndActions() {
    Map<String, Map<String,Object>> functions = new HashMap<>();
    for (Map<String,Object> tool : model.toolDefinitions()) {
      @SuppressWarnings("unchecked") Map<String,Object> function = (Map<String,Object>) tool.get("function");
      functions.put((String) function.get("name"), function);
    }
    assertThat(schema(functions,"get_today_summary").get("additionalProperties")).isEqualTo(false);
    assertThat(required(functions,"search_entries")).isEmpty();
    assertThat(required(functions,"get_entry")).containsExactly("entryId");
    assertThat(required(functions,"create_food_entry")).containsExactly("items");
    assertThat(required(functions,"prepare_entry_delete")).containsExactly("entryId");
  }

  @Test void mealHistoryPromptRoutesRomanianAndEnglishToEntryListing() {
    assertThat(model.instructions(true)).contains("ce am mancat azi", "what did I eat today", "call search_entries with no query", "do not return only a summary");
  }

  @Test void sendsTodayMealListingContractAndParsesItsToolCall() {
    RestClient.Builder builder = RestClient.builder();
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    OpenAiJournalAgentModel live = new OpenAiJournalAgentModel(builder, new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","key","test"), new ObjectMapper());
    server.expect(requestTo("https://api.openai.com/v1/chat/completions"))
        .andExpect(method(org.springframework.http.HttpMethod.POST))
        .andExpect(content().string(org.hamcrest.Matchers.allOf(
            org.hamcrest.Matchers.containsString("ce am mancat azi"),
            org.hamcrest.Matchers.containsString("call search_entries with no query"),
            org.hamcrest.Matchers.containsString("Omit query to list today's meals"))))
        .andRespond(withSuccess("{\"choices\":[{\"message\":{\"content\":null,\"tool_calls\":[{\"id\":\"call_1\",\"type\":\"function\",\"function\":{\"name\":\"search_entries\",\"arguments\":\"{}\"}}]}}]}", MediaType.APPLICATION_JSON));

    var reply = live.next(new AgentContext(new io.github.foodjournal.domain.FoodUser(1,"Vlad"),1,true,"ce am mancat azi"), List.of(), List.of());

    assertThat(reply.toolCalls()).extracting(call -> call.name()).containsExactly("search_entries");
    assertThat(reply.toolCalls().getFirst().arguments()).isEqualTo("{}");
    server.verify();
  }

  @SuppressWarnings("unchecked") private Map<String,Object> schema(Map<String,Map<String,Object>> functions,String name) {
    return (Map<String,Object>) functions.get(name).get("parameters");
  }
  @SuppressWarnings("unchecked") private List<String> required(Map<String,Map<String,Object>> functions,String name) { return (List<String>) schema(functions,name).get("required"); }
}
