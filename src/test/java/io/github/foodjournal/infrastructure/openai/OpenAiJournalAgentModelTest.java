package io.github.foodjournal.infrastructure.openai;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.config.BotProperties;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

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

  @Test void toolDefinitionsExposeTypedArgumentsForSensorsAndActions() {
    Map<String, Map<String,Object>> functions = new HashMap<>();
    for (Map<String,Object> tool : model.toolDefinitions()) {
      @SuppressWarnings("unchecked") Map<String,Object> function = (Map<String,Object>) tool.get("function");
      functions.put((String) function.get("name"), function);
    }
    assertThat(schema(functions,"get_today_summary").get("additionalProperties")).isEqualTo(false);
    assertThat(required(functions,"search_entries")).containsExactly("query");
    assertThat(required(functions,"get_entry")).containsExactly("entryId");
    assertThat(required(functions,"create_food_entry")).containsExactly("items");
    assertThat(required(functions,"prepare_entry_delete")).containsExactly("entryId");
  }

  @SuppressWarnings("unchecked") private Map<String,Object> schema(Map<String,Map<String,Object>> functions,String name) {
    return (Map<String,Object>) functions.get(name).get("parameters");
  }
  @SuppressWarnings("unchecked") private List<String> required(Map<String,Map<String,Object>> functions,String name) { return (List<String>) schema(functions,name).get("required"); }
}
