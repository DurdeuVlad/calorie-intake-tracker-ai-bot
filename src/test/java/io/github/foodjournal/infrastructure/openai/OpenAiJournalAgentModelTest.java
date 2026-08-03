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

  @Test void helpfulPromptUsesContextAndResolvesNutritionWithoutPingPong() {
    String prompt = model.instructions(true);
    assertThat(prompt).contains("Reduce the user's effort", "When the user asks for something useful, clear, and possible with the available tools, do it", "same as before",
        "get_private_food/resolve_nutrition/lookup_food", "estimate without another back-and-forth",
        "A food-free calculation is not a meal", "clearly labelled reasonable nutrition estimate");
  }

  @Test void correctionPromptMutatesImmediatelyAndOnlyClarifiesRealAmbiguity() {
    assertThat(model.instructions(true)).contains("noteaza doar o data", "correction requests", "delete the accidental newer copy", "Ask one short clarification only when multiple plausible entries remain");
    assertThat(model.instructions(true)).contains("never ask for confirmation", "never mention pending, prepared, or confirmation states");
  }

  @Test void promptRequiresPlainSelfContainedTelegramReplies() {
    assertThat(model.instructions(true)).contains("Telegram is plain text", "never use Markdown or HTML", "do not append generic offers");
  }

  @Test void promptTreatsMemoryAsContextRatherThanAnUnfinishedTaskQueue() {
    assertThat(model.instructions(true)).contains("Conversation memory is background context", "The current user message is authoritative", "Never resume a stale meal");
  }


  @Test void toolDefinitionsExposeTypedArgumentsForSensorsAndActions() {
    Map<String, Map<String,Object>> functions = new HashMap<>();
    for (Map<String,Object> tool : model.toolDefinitions()) {
      @SuppressWarnings("unchecked") Map<String,Object> function = (Map<String,Object>) tool.get("function");
      functions.put((String) function.get("name"), function);
    }
    assertThat(schema(functions,"get_today_summary").get("additionalProperties")).isEqualTo(false);
    assertThat(required(functions,"search_entries")).isEmpty();
    assertThat(properties(functions,"search_entries")).containsKeys("query","date","fromDate","toDate");
    assertThat(required(functions,"get_entry")).containsExactly("entryId");
    assertThat(required(functions,"apply_journal_actions")).containsExactly("actions");
    assertThat(required(functions,"undo_last_change")).isEmpty();
    assertThat(functions).doesNotContainKeys("create_food_entry","prepare_entry_edit","prepare_entry_delete","move_entry","get_pending_action","confirm_pending_action");
    Map<String,Object> action = actionSchema(functions);
    assertThat(actionRequired(action)).containsExactly("type");
    assertThat(actionProperties(action)).containsKeys("type","entryId","description","calories","quantity","unit","date","localTime","quoteId","nutritionSource","nutritionConfidence");
  }

  @Test void promptBatchesMealsAcceptsDeclaredCaloriesAndUnderstandsYesterdayTypos() {
    assertThat(model.instructions(true)).contains("several CREATE actions together in one apply_journal_actions call", "total calories are sufficient", "Do not ask for grams", "yersterday", "undo_last_change", "For ml or portion quantities", "nutritionSource ai_estimate");
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
  @SuppressWarnings("unchecked") private Map<String,Object> properties(Map<String,Map<String,Object>> functions,String name) { return (Map<String,Object>) schema(functions,name).get("properties"); }
  @SuppressWarnings("unchecked") private Map<String,Object> actionSchema(Map<String,Map<String,Object>> functions) { Map<String,Object> actions=(Map<String,Object>)properties(functions,"apply_journal_actions").get("actions"); return (Map<String,Object>)actions.get("items"); }
  @SuppressWarnings("unchecked") private List<String> actionRequired(Map<String,Object> schema) { return (List<String>) schema.get("required"); }
  @SuppressWarnings("unchecked") private Map<String,Object> actionProperties(Map<String,Object> schema) { return (Map<String,Object>) schema.get("properties"); }
}
