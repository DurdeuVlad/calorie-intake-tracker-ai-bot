package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.FoodUser;
import java.util.*;
import org.junit.jupiter.api.Test;

class JournalAgentTest {
  @Test void makesToolsResultsAvailableBeforeReturningFinalReply() {
    JournalAgentModel model = mock(JournalAgentModel.class);
    JournalToolExecutor tools = mock(JournalToolExecutor.class);
    AgentContext context = new AgentContext(new FoodUser(1L, "Vlad"), 1L, true, "total azi?");
    JournalAgentModel.ToolCall call = new JournalAgentModel.ToolCall("c1", "get_today_summary", "{}");
    when(model.next(eq(context), anyList(), argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null, List.of(call)));
    when(tools.execute(eq(context), eq(call), anyList())).thenReturn(AgentToolResult.ok(Map.of("calories", 425)));
    when(model.next(eq(context), anyList(), argThat(history -> history.size() == 1 && history.getFirst().result().ok()))).thenReturn(new JournalAgentModel.AgentReply("Total azi: 425 kcal.", List.of()));
    String reply = new JournalAgent(model, tools, props()).run(context);
    assertThat(reply).isEqualTo("Total azi: 425 kcal.");
    verify(tools).execute(eq(context), eq(call), anyList());
  }

  @Test void stopsBeforeAnEleventhToolCall() {
    JournalAgentModel model = mock(JournalAgentModel.class);
    JournalToolExecutor tools = mock(JournalToolExecutor.class);
    AgentContext context = new AgentContext(new FoodUser(1L, "Vlad"), 1L, true, "test");
    JournalAgentModel.ToolCall call = new JournalAgentModel.ToolCall("c", "get_settings", "{}");
    when(model.next(eq(context), anyList(), anyList())).thenReturn(new JournalAgentModel.AgentReply(null, List.of(call, call)));
    when(tools.execute(any(), any(), anyList())).thenReturn(AgentToolResult.ok(Map.of()));
    assertThat(new JournalAgent(model, tools, props()).run(context)).contains("detaliu");
    verify(tools, times(10)).execute(any(), any(), anyList());
  }

  @Test void propagatesModelFailureSoTheWebhookTransactionCanRollback() {
    JournalAgentModel model = mock(JournalAgentModel.class);
    when(model.next(any(), anyList(), anyList())).thenThrow(new IllegalStateException("provider down"));
    assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> new JournalAgent(model, mock(JournalToolExecutor.class), props()).run(new AgentContext(new FoodUser(1L, "Vlad"), 1L, true, "test"))))
        .isInstanceOf(IllegalStateException.class);
  }

  @Test void romanianFirstBrandConversationSearchesThenLogsAnEstimate() {
    JournalAgentModel model=mock(JournalAgentModel.class); JournalToolExecutor tools=mock(JournalToolExecutor.class);
    AgentContext context=new AgentContext(new FoodUser(1L,"Vlad"),1L,true,"cauta prima marca si e ok");
    JournalAgentModel.ToolCall search=new JournalAgentModel.ToolCall("s","search_packaged_food","{\"name\":\"crenvusti\"}");
    JournalAgentModel.ToolCall create=new JournalAgentModel.ToolCall("c","create_food_entry","{\"items\":[{\"name\":\"Brand A\",\"grams\":50,\"caloriesPer100g\":250,\"nutritionMode\":\"PACKAGED_MATCH\"}]}");
    when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(search)));
    when(tools.execute(eq(context),eq(search),anyList())).thenReturn(AgentToolResult.ok(Map.of("products",List.of(Map.of("name","Brand A","caloriesPer100g",250,"barcode","12345678")))));
    when(model.next(eq(context),anyList(),argThat(history->history.size()==1))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(create)));
    when(tools.execute(eq(context),eq(create),anyList())).thenReturn(AgentToolResult.ok(Map.of("estimated",true,"today",Map.of("calories",125))));
    when(model.next(eq(context),anyList(),argThat(history->history.size()==2))).thenReturn(new JournalAgentModel.AgentReply("Am estimat 125 kcal; valoarea poate fi greșită.",List.of()));
    assertThat(new JournalAgent(model,tools,props()).run(context)).contains("Am estimat", "125 kcal");
    verify(tools).execute(eq(context),eq(search),anyList()); verify(tools).execute(eq(context),eq(create),anyList());
  }

  private BotProperties props() { return new BotProperties("t", "s", Set.of(1L), "Europe/Bucharest", "", "test"); }
}
