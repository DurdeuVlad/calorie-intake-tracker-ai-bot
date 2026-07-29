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
    when(model.next(eq(context), argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null, List.of(call)));
    when(tools.execute(eq(context), eq(call), anyList())).thenReturn(AgentToolResult.ok(Map.of("calories", 425)));
    when(model.next(eq(context), argThat(history -> history.size() == 1 && history.getFirst().result().ok()))).thenReturn(new JournalAgentModel.AgentReply("Total azi: 425 kcal.", List.of()));
    String reply = new JournalAgent(model, tools, props()).run(context);
    assertThat(reply).isEqualTo("Total azi: 425 kcal.");
    verify(tools).execute(eq(context), eq(call), anyList());
  }

  @Test void stopsBeforeAnEleventhToolCall() {
    JournalAgentModel model = mock(JournalAgentModel.class);
    JournalToolExecutor tools = mock(JournalToolExecutor.class);
    AgentContext context = new AgentContext(new FoodUser(1L, "Vlad"), 1L, true, "test");
    JournalAgentModel.ToolCall call = new JournalAgentModel.ToolCall("c", "get_settings", "{}");
    when(model.next(eq(context), anyList())).thenReturn(new JournalAgentModel.AgentReply(null, List.of(call, call)));
    when(tools.execute(any(), any(), anyList())).thenReturn(AgentToolResult.ok(Map.of()));
    assertThat(new JournalAgent(model, tools, props()).run(context)).contains("detaliu");
    verify(tools, times(10)).execute(any(), any(), anyList());
  }

  private BotProperties props() { return new BotProperties("t", "s", Set.of(1L), "Europe/Bucharest", "", "test"); }
}
