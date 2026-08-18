package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.ConversationMemory;
import io.github.foodjournal.domain.FoodUser;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

class JournalAgentTest {
  @Test void makesToolsResultsAvailableBeforeReturningFinalReply(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"total azi?");JournalAgentModel.ToolCall call=new JournalAgentModel.ToolCall("c1","get_today_summary","{}");when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(call)));when(tools.execute(eq(context),eq(call),anyList())).thenReturn(AgentToolResult.ok(Map.of("calories",425)));when(model.next(eq(context),anyList(),argThat(history->history.size()==1&&history.getFirst().result().ok()))).thenReturn(new JournalAgentModel.AgentReply("Total azi: 425 kcal.",List.of()));assertThat(new JournalAgent(model,tools,props()).run(context)).isEqualTo("Total azi: 425 kcal.");verify(tools).execute(eq(context),eq(call),anyList());}
  @Test void stopsBeforeAnEleventhToolCall(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"test");JournalAgentModel.ToolCall call=new JournalAgentModel.ToolCall("c","get_settings","{}");when(model.next(eq(context),anyList(),anyList())).thenReturn(new JournalAgentModel.AgentReply(null,List.of(call,call)));when(tools.execute(any(),any(),anyList())).thenReturn(AgentToolResult.ok(Map.of()));assertThat(new JournalAgent(model,tools,props()).run(context)).contains("detaliu");verify(tools,times(10)).execute(any(),any(),anyList());}
  @Test void returnsAGracefulReplyInsteadOfDroppingTheMessageWhenTheModelCallFails(){JournalAgentModel model=mock(JournalAgentModel.class);when(model.next(any(),anyList(),anyList())).thenThrow(new IllegalStateException("provider down"));assertThat(new JournalAgent(model,mock(JournalToolExecutor.class),props()).run(new AgentContext(new FoodUser(1,"Vlad"),1,true,"test"))).contains("Nu pot procesa cererea acum");}
  @Test void appliesSeveralMealCreationsInOneBatch(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"600 kcal mic dejun si 1000 kcal cina");JournalAgentModel.ToolCall batch=new JournalAgentModel.ToolCall("b","apply_journal_actions","{\"actions\":[{\"type\":\"CREATE\",\"description\":\"mic dejun\",\"calories\":600},{\"type\":\"CREATE\",\"description\":\"cina\",\"calories\":1000}]}");when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(batch)));when(tools.execute(eq(context),eq(batch),anyList())).thenReturn(AgentToolResult.ok(Map.of("results",List.of(Map.of("ok",true,"type","CREATE","entry",Map.of("description","mic dejun","calories",600),"date","2026-08-02"),Map.of("ok",true,"type","CREATE","entry",Map.of("description","cina","calories",1000),"date","2026-08-02")),"undoAvailable",true)));assertThat(new JournalAgent(model,tools,props()).run(context)).contains("mic dejun","cina","Undo");verify(tools).execute(eq(context),eq(batch),anyList());}
  @Test void romanianOnlyOnceRequestDeletesDuplicateImmediately(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"noteaza doar 50 g de crenvusti odata te rog");JournalAgentModel.ToolCall search=new JournalAgentModel.ToolCall("s","search_entries","{\"query\":\"crenvusti\"}");JournalAgentModel.ToolCall delete=new JournalAgentModel.ToolCall("d","apply_journal_actions","{\"actions\":[{\"type\":\"DELETE\",\"entryId\":12}]}");when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(search)));when(tools.execute(eq(context),eq(search),anyList())).thenReturn(AgentToolResult.ok(Map.of("entries",List.of(Map.of("id",11,"description","50g crenvusti","calories",125),Map.of("id",12,"description","50g crenvusti","calories",125)))));when(model.next(eq(context),anyList(),argThat(h->h.size()==1))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(delete)));when(tools.execute(eq(context),eq(delete),anyList())).thenReturn(AgentToolResult.ok(Map.of("results",List.of(Map.of("ok",true,"type","DELETE","entry",Map.of("description","50g crenvusti","calories",125),"date","2026-08-02")),"undoAvailable",true)));assertThat(new JournalAgent(model,tools,props()).run(context)).contains("125 kcal","Undo").doesNotContain("confirm");}
  @Test void romanianFirstBrandFollowUpReadsThenConsumesServerOwnedQuote(){JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);AgentContext context=new AgentContext(new FoodUser(1,"Vlad"),1,true,"cauta prima marca si e ok");String quoteId="00000000-0000-0000-0000-000000000042";JournalAgentModel.ToolCall pending=new JournalAgentModel.ToolCall("p","get_pending_nutrition_quotes","{}");JournalAgentModel.ToolCall select=new JournalAgentModel.ToolCall("s","select_packaged_food","{\"quoteId\":\""+quoteId+"\"}");JournalAgentModel.ToolCall create=new JournalAgentModel.ToolCall("c","create_food_entry","{\"items\":[{\"nutritionMode\":\"PACKAGED_MATCH\",\"quoteId\":\""+quoteId+"\"}]}");when(model.next(eq(context),anyList(),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(pending)));when(tools.execute(eq(context),eq(pending),anyList())).thenReturn(AgentToolResult.ok(Map.of("quotes",List.of(Map.of("quoteId",quoteId,"name","Brand A","caloriesPer100g",250)))));when(model.next(eq(context),anyList(),argThat(h->h.size()==1))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(select)));when(tools.execute(eq(context),eq(select),anyList())).thenReturn(AgentToolResult.ok(Map.of("quoteId",quoteId,"item",Map.of("totalCalories",125))));when(model.next(eq(context),anyList(),argThat(h->h.size()==2))).thenReturn(new JournalAgentModel.AgentReply(null,List.of(create)));when(tools.execute(eq(context),eq(create),anyList())).thenReturn(AgentToolResult.ok(Map.of("estimated",true,"today",Map.of("calories",125))));when(model.next(eq(context),anyList(),argThat(h->h.size()==3))).thenReturn(new JournalAgentModel.AgentReply("Am estimat 125 kcal; valoarea poate fi gresita.",List.of()));assertThat(new JournalAgent(model,tools,props()).run(context)).contains("Am estimat","125 kcal");verify(tools).execute(eq(context),eq(pending),anyList());verify(tools).execute(eq(context),eq(select),anyList());verify(tools).execute(eq(context),eq(create),anyList());}
  @Test void fallsBackToOriginalMealWhenUserGivesNoDigitsAfterAPortionQuestion(){
    FoodUser user=new FoodUser(1,"Vlad");
    ConversationMemory askedForGrams=new ConversationMemory(user,"assistant","Cate grame are burrito-ul?");
    ConversationMemory originalMeal=new ConversationMemory(user,"user","Am mancat un burrito mare de la Taco Bell");
    List<ConversationMemory> recent=List.of(originalMeal,askedForGrams);
    JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);
    ConversationMemoryService memory=mock(ConversationMemoryService.class);when(memory.recent(eq(user))).thenReturn(recent);
    MeterRegistry metrics=mock(MeterRegistry.class);when(metrics.counter(anyString())).thenReturn(mock(Counter.class));
    ObjectProvider<AgentTraceSink> traces=mock(ObjectProvider.class);when(traces.getIfAvailable(any())).thenReturn(AgentTraceSink.noop());
    AgentContext context=new AgentContext(user,1,true,"Scrie tu, conteaza doar caloriile");
    AgentContext rewritten=new AgentContext(user,1,true,"Estimate this meal now: Am mancat un burrito mare de la Taco Bell",context.startedAt());
    when(model.next(eq(rewritten),eq(recent),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply("Am notat burrito-ul: 700 kcal.",List.of()));
    JournalAgent agent=new JournalAgent(model,tools,props(),metrics,memory,traces);
    assertThat(agent.run(context)).contains("700 kcal");
    verify(model).next(eq(rewritten),eq(recent),anyList());
  }
  @Test void doesNotRewriteWhenUserSuppliesANumberEvenWithoutTheDeclineKeywords(){
    FoodUser user=new FoodUser(1,"Vlad");
    ConversationMemory askedForGrams=new ConversationMemory(user,"assistant","Cate grame are burrito-ul?");
    ConversationMemory originalMeal=new ConversationMemory(user,"user","Am mancat un burrito mare de la Taco Bell");
    List<ConversationMemory> recent=List.of(originalMeal,askedForGrams);
    JournalAgentModel model=mock(JournalAgentModel.class);JournalToolExecutor tools=mock(JournalToolExecutor.class);
    ConversationMemoryService memory=mock(ConversationMemoryService.class);when(memory.recent(eq(user))).thenReturn(recent);
    MeterRegistry metrics=mock(MeterRegistry.class);when(metrics.counter(anyString())).thenReturn(mock(Counter.class));
    ObjectProvider<AgentTraceSink> traces=mock(ObjectProvider.class);when(traces.getIfAvailable(any())).thenReturn(AgentTraceSink.noop());
    AgentContext context=new AgentContext(user,1,true,"Baga 1200 kcal impartit la ele");
    when(model.next(eq(context),eq(recent),argThat(List::isEmpty))).thenReturn(new JournalAgentModel.AgentReply("Am notat: 1200 kcal.",List.of()));
    JournalAgent agent=new JournalAgent(model,tools,props(),metrics,memory,traces);
    assertThat(agent.run(context)).contains("1200 kcal");
    verify(model).next(eq(context),eq(recent),anyList());
  }
  private BotProperties props(){return new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","","test");}
}
