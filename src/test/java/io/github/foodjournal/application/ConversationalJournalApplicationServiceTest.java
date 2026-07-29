package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.*;

class ConversationalJournalApplicationServiceTest {
 private FoodUserRepository users=mock(FoodUserRepository.class); private UserSettingsRepository settings=mock(UserSettingsRepository.class); private FoodEntryRepository entries=mock(FoodEntryRepository.class); private FoodItemRepository items=mock(FoodItemRepository.class); private PrivateFoodRepository privateFoods=mock(PrivateFoodRepository.class); private IntentInterpreter interpreter=mock(IntentInterpreter.class); private DailyStatusService status=mock(DailyStatusService.class); private PendingFoodDraftRepository drafts=mock(PendingFoodDraftRepository.class); private FoodUser user=new FoodUser(1L,"Vlad"); private JournalApplicationService service;
 @BeforeEach void setUp(){service=new JournalApplicationService(users,settings,entries,items,privateFoods,interpreter,new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","","test"),status,(u,item)->{int total=item.caloriesPer100g()==null?item.totalCalories():(int)Math.round(item.grams()*item.caloriesPer100g()/100d);return new NutritionResolver.ResolvedMealItem(new JournalIntent.MealItem(item.name(),item.grams(),total,item.caloriesPer100g(),item.proteinGrams(),item.carbsGrams(),item.fatGrams(),item.barcode()),"manual");},drafts);UserSettings profile=new UserSettings(user,"Europe/Bucharest");profile.completeOnboarding();when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));when(settings.findById(any())).thenReturn(Optional.of(profile));when(entries.save(any())).thenAnswer(i->i.getArgument(0));when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of());}
 @Test void calculatesPerHundredGramFoodsLocallyAndRepliesInRomanian(){when(interpreter.interpret(anyString())).thenReturn(new JournalIntent(IntentType.LOG_MEAL,"crispy cu sos",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("crispy iute",165d,null,229,null,null,null,null),new JournalIntent.MealItem("sos Piripi",25d,null,188,null,null,null,null))));String reply=service.handle(1L,1L,"Vlad","adauga 165 g crispy iute, 229 kcal la 100 g și 25 g sos, 188 kcal la 100 g");assertThat(reply).contains("425 kcal").contains("378 kcal").contains("47 kcal");verify(entries).save(argThat(entry->entry.getCalories()==425));verify(items,times(2)).save(any());}
 @Test void answersRomanianTodayTotalFromTheDeterministicCommand(){FoodEntry entry=new FoodEntry(user,"lapte",Instant.now(),297,"manual","high");when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of(entry));assertThat(service.handle(1L,1L,"Vlad","/today")).contains("Total azi: 297 kcal");verifyNoInteractions(interpreter);}
 @Test void resumesAUniqueRecentDraft(){PendingFoodDraft draft=new PendingFoodDraft(user,"165 g crispy",Instant.now());when(drafts.findByUserAndExpiresAtAfter(eq(user),any())).thenReturn(Optional.of(draft));when(interpreter.interpret("165 g crispy")).thenReturn(new JournalIntent(IntentType.LOG_MEAL,"crispy",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("crispy",165d,378))));assertThat(service.handle(1L,1L,"Vlad","adaugă ce ți-am cerut")).contains("378 kcal");verify(interpreter).interpret("165 g crispy");verify(drafts).deleteByUser(user);}
 @Test void purgesExpiredRawDraftsBeforeHandlingAnUpdate(){when(interpreter.interpret("hello")).thenReturn(new JournalIntent(IntentType.CHAT,null,null,null,null,null,null,null,List.of()));service.handle(1L,1L,"Vlad","hello");verify(drafts).deleteByExpiresAtBefore(any(Instant.class));}
}
