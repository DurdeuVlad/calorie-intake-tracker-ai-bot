package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.FoodUser;
import java.util.*;
import org.junit.jupiter.api.Test;

class TodayMealListAgentTest {
  @Test void romanianWhatDidIEatTodayListsEntriesInsteadOfOnlySummary(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"ce am mancat azi");JournalAgentModel.ToolCall list=new JournalAgentModel.ToolCall("l","search_entries","{}");when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(list)));when(tools.execute(eq(context),eq(list),anyList())).thenReturn(AgentToolResult.ok(Map.of("entries",List.of(Map.of("id",1,"description","50 g crenvusti","calories",125),Map.of("id",2,"description","pui cu legume","calories",270)))));when(model.next(eq(context),anyList(),argThat(history->history.size()==1))).thenReturn(new JournalAgentModel.AgentReply("Azi ai mâncat: 50 g crenvuști — 125 kcal; pui cu legume — 270 kcal.",List.of()));String answer=new JournalAgent(model,tools,props()).run(context);assertThat(answer).contains("50 g crenvuști", "pui cu legume");verify(tools,never()).execute(eq(context),argThat(call->"get_today_summary".equals(call.name())),anyList());}
  private BotProperties props(){return new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","","test");}
}
