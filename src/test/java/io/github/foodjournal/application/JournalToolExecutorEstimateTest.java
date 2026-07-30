package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class JournalToolExecutorEstimateTest {
  private FoodEntryRepository entries=mock(FoodEntryRepository.class); private FoodItemRepository items=mock(FoodItemRepository.class);
  private UserSettingsRepository settings=mock(UserSettingsRepository.class); private DailyStatusService status=mock(DailyStatusService.class);
  private JournalToolExecutor executor; private FoodUser user=new FoodUser(1,"Vlad");
  @BeforeEach void setUp(){UserSettings profile=new UserSettings(user,"Europe/Bucharest");when(settings.findById(any())).thenReturn(Optional.of(profile));when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(any(),any(),any())).thenReturn(List.of());FoodEntry saved=mock(FoodEntry.class);when(saved.getId()).thenReturn(9L);when(saved.getCalories()).thenReturn(125);when(saved.getEatenAt()).thenReturn(Instant.EPOCH);when(saved.getOriginalMessage()).thenReturn("50g crenvusti");when(entries.save(any())).thenReturn(saved);NutritionResolver resolver=(u,i)->new NutritionResolver.ResolvedMealItem(new JournalIntent.MealItem(i.name(),i.grams(),i.caloriesPer100g()==null?i.totalCalories():(int)Math.round(i.grams()*i.caloriesPer100g()/100d),i.caloriesPer100g(),null,null,null,i.barcode()),"manual");executor=new JournalToolExecutor(new ObjectMapper(),settings,entries,items,mock(PrivateFoodRepository.class),resolver,status,mock(PendingAgentActionRepository.class));}
  @Test void estimateCalculatesServerSideWithoutWriting(){AgentToolResult result=execute("estimate_food","{\"name\":\"crenvusti\",\"grams\":50,\"caloriesPer100g\":250}");assertThat(result.ok()).isTrue();assertThat(result.data()).containsEntry("basis","AI estimate");@SuppressWarnings("unchecked") Map<String,Object> item=(Map<String,Object>)result.data().get("item");assertThat(item).containsEntry("totalCalories",125).containsEntry("confidence","estimate");verifyNoInteractions(entries,items,status);}
  @Test void packagedMatchPersistsEstimatedProvenanceAndRecalculatesCalories(){AgentToolResult result=execute("create_food_entry","{\"items\":[{\"name\":\"Crenvusti\",\"grams\":50,\"caloriesPer100g\":250,\"totalCalories\":999,\"nutritionMode\":\"PACKAGED_MATCH\"}]}");assertThat(result.ok()).isTrue();ArgumentCaptor<FoodEntry> entry=ArgumentCaptor.forClass(FoodEntry.class);verify(entries).save(entry.capture());assertThat(entry.getValue().getCalories()).isEqualTo(125);assertThat(entry.getValue().getNutritionSource()).isEqualTo("open_food_facts_estimate");assertThat(entry.getValue().getConfidence()).isEqualTo("estimate");ArgumentCaptor<FoodItem> item=ArgumentCaptor.forClass(FoodItem.class);verify(items).save(item.capture());assertThat(item.getValue().getNutritionSource()).isEqualTo("open_food_facts_estimate");}
  @Test void invalidEstimateDoesNotWrite(){AgentToolResult result=execute("create_food_entry","{\"items\":[{\"name\":\"Crenvusti\",\"grams\":50,\"caloriesPer100g\":0,\"nutritionMode\":\"AI_ESTIMATE\"}]}");assertThat(result.ok()).isFalse();assertThat(result.code()).isEqualTo("VALIDATION_ERROR");verifyNoInteractions(entries,items,status);}
  private AgentToolResult execute(String name,String arguments){return executor.execute(new AgentContext(user,1,true,"50g crenvusti",Instant.now()),new JournalAgentModel.ToolCall("call",name,arguments),new ArrayList<>());}
}
