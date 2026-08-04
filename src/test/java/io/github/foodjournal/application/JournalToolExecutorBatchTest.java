package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

class JournalToolExecutorBatchTest {
  private final FoodEntryRepository entries=mock(FoodEntryRepository.class);
  private final FoodItemRepository items=mock(FoodItemRepository.class);
  private final UserSettingsRepository settings=mock(UserSettingsRepository.class);
  private final DailyStatusService status=mock(DailyStatusService.class);
  private final JournalChangeSetRepository changeSets=mock(JournalChangeSetRepository.class);
  private final FoodUser user=new FoodUser(1,"Vlad");
  private JournalToolExecutor executor;
  private final Instant startedAt=Instant.parse("2026-08-02T12:00:00Z");

  @BeforeEach void setUp(){
    when(settings.findById(any())).thenReturn(Optional.of(new UserSettings(user,"Europe/Bucharest")));
    AtomicLong ids=new AtomicLong(10);when(entries.save(any(FoodEntry.class))).thenAnswer(call->{FoodEntry entry=call.getArgument(0);ReflectionTestUtils.setField(entry,"id",ids.getAndIncrement());return entry;});
    when(items.save(any(FoodItem.class))).thenAnswer(call->{FoodItem item=call.getArgument(0);ReflectionTestUtils.setField(item,"id",ids.getAndIncrement());return item;});
    executor=new JournalToolExecutor(new ObjectMapper(),settings,entries,items,mock(PrivateFoodRepository.class),NutritionResolver.noop(),status,mock(PendingAgentActionRepository.class),null,mock(PendingNutritionQuoteRepository.class),mock(NutritionSourceCacheRepository.class),mock(JournalUndoActionRepository.class),changeSets,null,null);
  }

  @Test void createsSeveralEntriesWithoutQuantitiesAndBackdatesThem(){
    AgentToolResult result=execute("apply_journal_actions","""
        {"actions":[
          {"type":"CREATE","description":"mic dejun","calories":600,"date":"yesterday"},
          {"type":"CREATE","description":"snacks","calories":300,"date":"ieri"},
          {"type":"CREATE","description":"cina","calories":1000,"date":"2026-08-01"}
        ]}
        """);
    assertThat(result.ok()).isTrue();assertThat(result.data()).containsEntry("successful",3).containsEntry("failed",0).containsEntry("undoAvailable",true);
    ArgumentCaptor<FoodEntry> saved=ArgumentCaptor.forClass(FoodEntry.class);verify(entries,times(3)).save(saved.capture());
    assertThat(saved.getAllValues()).allMatch(entry->entry.getEatenAt().atZone(ZoneId.of("Europe/Bucharest")).toLocalDate().equals(LocalDate.of(2026,8,1)));
    ArgumentCaptor<FoodItem> food=ArgumentCaptor.forClass(FoodItem.class);verify(items,times(3)).save(food.capture());assertThat(food.getAllValues()).allMatch(item->item.getQuantity()==null&&item.getQuantityUnit()==QuantityUnit.UNSPECIFIED);
  }

  @Test void keepsSuccessfulActionsWhenAnotherActionTargetsTheFuture(){
    AgentToolResult result=execute("apply_journal_actions","""
        {"actions":[
          {"type":"CREATE","description":"pranz","calories":500,"date":"today"},
          {"type":"CREATE","description":"desert","calories":300,"date":"2026-08-03"}
        ]}
        """);
    assertThat(result.data()).containsEntry("successful",1).containsEntry("failed",1);verify(entries).save(any(FoodEntry.class));verify(changeSets).saveAndFlush(argThat(set->set.getMutations().size()==1));
  }

  @Test void preservesMillilitresForATransparentYesterdayEstimateAndAcceptsTheCommonTypo(){
    AgentToolResult result=execute("apply_journal_actions","{\"actions\":[{\"type\":\"CREATE\",\"description\":\"rom Bumbu\",\"calories\":140,\"quantity\":60,\"unit\":\"ml\",\"date\":\"yersterday\",\"nutritionSource\":\"ai_estimate\",\"nutritionConfidence\":\"estimate\"}]}");
    assertThat(result.data()).containsEntry("successful",1);
    ArgumentCaptor<FoodItem> saved=ArgumentCaptor.forClass(FoodItem.class);verify(items).save(saved.capture());assertThat(saved.getValue().getQuantity()).isEqualByComparingTo("60");assertThat(saved.getValue().getQuantityUnit()).isEqualTo(QuantityUnit.ML);assertThat(saved.getValue().getNutritionSource()).isEqualTo("ai_estimate");
  }

  @Test void rejectsANonexistentLocalTimeDuringTheDstGap(){
    Instant afterDstGap=Instant.parse("2026-03-30T12:00:00Z");
    AgentToolResult result=executor.execute(new AgentContext(user,1,true,"test",afterDstGap),new JournalAgentModel.ToolCall("call","apply_journal_actions","{\"actions\":[{\"type\":\"CREATE\",\"description\":\"masa\",\"calories\":400,\"date\":\"2026-03-29\",\"localTime\":\"03:30\"}]}"),new ArrayList<>());
    assertThat(result.data()).containsEntry("successful",0).containsEntry("failed",1);verify(entries,never()).save(any());
  }

  @Test void usesTheEarlierOffsetForAnAmbiguousDstOverlap(){
    Instant afterOverlap=Instant.parse("2026-11-01T12:00:00Z");
    AgentToolResult result=executor.execute(new AgentContext(user,1,true,"test",afterOverlap),new JournalAgentModel.ToolCall("call","apply_journal_actions","{\"actions\":[{\"type\":\"CREATE\",\"description\":\"masa\",\"calories\":400,\"date\":\"2026-10-25\",\"localTime\":\"03:30\"}]}"),new ArrayList<>());
    assertThat(result.data()).containsEntry("successful",1);ArgumentCaptor<FoodEntry> saved=ArgumentCaptor.forClass(FoodEntry.class);verify(entries).save(saved.capture());assertThat(saved.getValue().getEatenAt()).isEqualTo(Instant.parse("2026-10-25T00:30:00Z"));
  }

  @Test void movesImmediatelyAndUndoRestoresTheWholeEntry(){
    FoodEntry salad=new FoodEntry(user,"salata",startedAt,350,"manual","high");ReflectionTestUtils.setField(salad,"id",42L);
    FoodItem item=new FoodItem(salad,"salata",null,QuantityUnit.UNSPECIFIED,350,null,null,null,"manual","high");ReflectionTestUtils.setField(item,"id",43L);
    when(entries.findByIdAndUser(42L,user)).thenReturn(Optional.of(salad));when(entries.findIncludingDeletedByIdAndUser(42L,user)).thenReturn(Optional.of(salad));when(items.findByEntry(salad)).thenReturn(List.of(item));
    ArgumentCaptor<JournalChangeSet> savedSet=ArgumentCaptor.forClass(JournalChangeSet.class);when(changeSets.saveAndFlush(savedSet.capture())).thenAnswer(call->call.getArgument(0));
    AgentToolResult moved=execute("apply_journal_actions","{\"actions\":[{\"type\":\"MOVE\",\"entryId\":42,\"date\":\"yesterday\"}]}");
    assertThat(moved.data()).containsEntry("successful",1);assertThat(salad.getEatenAt().atZone(ZoneId.of("Europe/Bucharest")).toLocalDate()).isEqualTo(LocalDate.of(2026,8,1));
    when(changeSets.findFirstByUserAndUndoneAtIsNullAndExpiresAtAfterOrderByCreatedAtDescIdDesc(eq(user),any())).thenReturn(Optional.of(savedSet.getValue()));
    AgentToolResult undone=execute("undo_last_change","{}");
    assertThat(undone.ok()).isTrue();assertThat(salad.getEatenAt()).isEqualTo(startedAt);assertThat(savedSet.getValue().getUndoneAt()).isEqualTo(startedAt);
  }

  @Test void editKeepsTheEntryAndItsSingleItemConsistentAndUndoRestoresBoth(){
    FoodEntry meal=new FoodEntry(user,"old meal",startedAt,350,"manual","high");ReflectionTestUtils.setField(meal,"id",52L);FoodItem item=new FoodItem(meal,"old meal",null,QuantityUnit.UNSPECIFIED,350,null,null,null,"manual","high");ReflectionTestUtils.setField(item,"id",53L);
    when(entries.findByIdAndUser(52L,user)).thenReturn(Optional.of(meal));when(entries.findIncludingDeletedByIdAndUser(52L,user)).thenReturn(Optional.of(meal));when(items.findByEntry(meal)).thenReturn(List.of(item));ArgumentCaptor<JournalChangeSet> savedSet=ArgumentCaptor.forClass(JournalChangeSet.class);when(changeSets.saveAndFlush(savedSet.capture())).thenAnswer(call->call.getArgument(0));
    AgentToolResult edited=execute("apply_journal_actions","{\"actions\":[{\"type\":\"EDIT\",\"entryId\":52,\"description\":\"new meal\",\"calories\":500}]}");assertThat(edited.data()).containsEntry("successful",1);assertThat(meal.getOriginalMessage()).isEqualTo("new meal");assertThat(meal.getCalories()).isEqualTo(500);assertThat(item.getName()).isEqualTo("new meal");assertThat(item.getCalories()).isEqualTo(500);
    when(changeSets.findFirstByUserAndUndoneAtIsNullAndExpiresAtAfterOrderByCreatedAtDescIdDesc(eq(user),any())).thenReturn(Optional.of(savedSet.getValue()));execute("undo_last_change","{}");assertThat(meal.getOriginalMessage()).isEqualTo("old meal");assertThat(meal.getCalories()).isEqualTo(350);ArgumentCaptor<FoodItem> restored=ArgumentCaptor.forClass(FoodItem.class);verify(items).save(restored.capture());assertThat(restored.getValue().getName()).isEqualTo("old meal");assertThat(restored.getValue().getCalories()).isEqualTo(350);
  }

  @Test void cannotMutateAnEntryOwnedBySomeoneElse(){
    AgentToolResult result=execute("apply_journal_actions","{\"actions\":[{\"type\":\"DELETE\",\"entryId\":99}]}");
    assertThat(result.data()).containsEntry("successful",0).containsEntry("failed",1);verify(entries,never()).delete(any());verify(changeSets,never()).saveAndFlush(any());
  }

  @Test void infrastructureFailureAbortsTheBatchInsteadOfReportingRolledBackSuccess(){
    doThrow(new IllegalStateException("database unavailable")).when(entries).flush();
    assertThat(org.assertj.core.api.Assertions.catchThrowable(()->execute("apply_journal_actions","{\"actions\":[{\"type\":\"CREATE\",\"description\":\"meal\",\"calories\":500}]}"))).isInstanceOf(IllegalStateException.class).hasMessageContaining("database unavailable");verify(changeSets,never()).saveAndFlush(any());
  }

  private AgentToolResult execute(String name,String arguments){return executor.execute(new AgentContext(user,1,true,"test",startedAt),new JournalAgentModel.ToolCall("call",name,arguments),new ArrayList<>());}
}
