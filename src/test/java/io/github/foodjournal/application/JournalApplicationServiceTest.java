package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.FoodEntry;
import io.github.foodjournal.domain.FoodUser;
import io.github.foodjournal.domain.UserSettings;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.repository.FoodEntryRepository;
import io.github.foodjournal.repository.FoodUserRepository;
import io.github.foodjournal.repository.UserSettingsRepository;
import io.github.foodjournal.repository.FoodItemRepository;
import io.github.foodjournal.repository.PrivateFoodRepository;
import io.github.foodjournal.repository.PendingFoodDraftRepository;
import io.github.foodjournal.repository.PendingAgentActionRepository;
import io.github.foodjournal.domain.FoodItem;
import io.github.foodjournal.domain.PrivateFood;
import io.github.foodjournal.application.DailyStatusService;
import java.util.List;
import java.util.Optional; import java.util.Set;
import java.time.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class JournalApplicationServiceTest {
  @Mock FoodUserRepository users;
  @Mock UserSettingsRepository settings;
  @Mock FoodEntryRepository entries;
  @Mock FoodItemRepository items;
  @Mock PrivateFoodRepository privateFoods;
  @Mock IntentInterpreter interpreter;
  @Mock DailyStatusService dailyStatus;
  @Mock PendingFoodDraftRepository drafts;
  @Mock PendingAgentActionRepository pendingActions;
  private JournalApplicationService service;

  @BeforeEach void setUp() { service = new JournalApplicationService(users, settings, entries, items, privateFoods, interpreter, new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), dailyStatus, NutritionResolver.noop(), drafts, pendingActions, null); }
  private void configured(FoodUser user){UserSettings value=new UserSettings(user,"Europe/Bucharest");value.completeOnboarding();when(settings.findById(user.getId())).thenReturn(Optional.of(value));}

  @Test void rejectsInvalidCaloriesWithoutWriting() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret("huge meal")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "huge meal", 10001, null, null, null, null, null, List.of()));

    assertThat(service.handle(1L, 1L, "A", "huge meal")).contains("Tell me");
    verify(entries, never()).save(any());
  }

  @Test void cannotDeleteAnotherUsersEntry() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret("delete 99")).thenReturn(new JournalIntent(IntentType.DELETE_ENTRY, null, null, null, 99L, null, null, null, List.of()));
    when(entries.findByIdAndUser(99L, user)).thenReturn(Optional.empty());

    assertThat(service.handle(1L, 1L, "A", "delete 99")).contains("could not find");
    verify(entries, never()).delete(any());
  }

  @Test void persistsValidMealForTheRequestingUserOnly() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret("I ate soup")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "vegetable soup", 220, null, null, null, null, null, List.of(new JournalIntent.MealItem("soup",300d,220))));
    when(entries.save(any(FoodEntry.class))).thenAnswer(invocation -> invocation.getArgument(0));

    assertThat(service.handle(1L, 1L, "A", "I ate soup")).contains("220 kcal");
    verify(entries).save(argThat(entry -> entry.getUser() == user && entry.getCalories() == 220));
  }

  @Test void persistsStructuredItemsWithTheMeal() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret("I ate soup and bread")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "soup and bread", 320, null, null, null, null, null, List.of(new JournalIntent.MealItem("soup", 300d, 220), new JournalIntent.MealItem("bread", 40d, 100))));
    when(entries.save(any(FoodEntry.class))).thenAnswer(invocation -> invocation.getArgument(0));

    service.handle(1L, 1L, "A", "I ate soup and bread");

    verify(items, times(2)).save(any(FoodItem.class));
  }

  @Test void marksMediaDerivedEntriesAsAiEstimates() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret(contains("Media-derived food evidence"))).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "oat bar", 180, null, null, null, null, null, List.of(new JournalIntent.MealItem("oat bar", 50d, 180))));
    when(entries.save(any(FoodEntry.class))).thenAnswer(invocation -> invocation.getArgument(0));

    assertThat(service.handleMediaEvidence(1L, 1L, "A", "Oat bar, 180 kcal")).contains("180 kcal");

    verify(entries).save(argThat(entry -> entry.getNutritionSource().equals("ai_estimate") && entry.getConfidence().equals("estimate")));
  }

  @Test void savesAHouseholdFoodForOnlyTheRequestingUser() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("save grandma soup")).thenReturn(new JournalIntent(IntentType.SAVE_PRIVATE_FOOD,"grandma soup",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("Grandma soup",100d,80,4d,10d,2d))));
    assertThat(service.handle(1L,1L,"A","save grandma soup")).isEqualTo("Saved household food: Grandma soup.");
    verify(privateFoods).save(argThat((PrivateFood food)->food.getName().equals("Grandma soup")&&food.getCaloriesPer100g()==80));
  }

  @Test void updatesAnExistingHouseholdFoodWithoutDeletingIt() {
    FoodUser user = new FoodUser(1L, "A"); PrivateFood existing = new PrivateFood(user,"Grandma soup",80,null,null,null); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("update grandma soup")).thenReturn(new JournalIntent(IntentType.SAVE_PRIVATE_FOOD,"grandma soup",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("Grandma soup",100d,90,4d,11d,2d)))); when(privateFoods.findByUserAndNameIgnoreCase(user,"Grandma soup")).thenReturn(Optional.of(existing));
    service.handle(1L,1L,"A","update grandma soup");
    assertThat(existing.getCaloriesPer100g()).isEqualTo(90); verify(privateFoods,never()).delete(any()); verify(privateFoods,never()).save(any());
  }

  @Test void rejectsInvalidHouseholdFoodMacrosWithoutWriting() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("save bad soup")).thenReturn(new JournalIntent(IntentType.SAVE_PRIVATE_FOOD,"bad",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("Bad soup",100d,80,Double.NaN,10d,2d))));
    assertThat(service.handle(1L,1L,"A","save bad soup")).contains("valid nutrition"); verifyNoInteractions(privateFoods);
  }

  @Test void searchesOnlyTheRequestingUsersJournal() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("find soup")).thenReturn(new JournalIntent(IntentType.QUERY_JOURNAL,null,null,"soup",null,null,null,null,List.of())); when(entries.searchByUserAndTerm(user,"soup")).thenReturn(List.of());
    assertThat(service.handle(1L,1L,"A","find soup")).isEqualTo("No matching entries found.");
    verify(entries).searchByUserAndTerm(user,"soup");
  }

  @Test void resolvesNaturalLanguageYesterdayWithinTheRequestingUsersTimezone() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("show yesterday")).thenReturn(new JournalIntent(IntentType.QUERY_JOURNAL,null,null,null,null,null,null,null,List.of())); when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of());
    assertThat(service.handle(1L,1L,"A","show yesterday")).isEqualTo("No matching entries found.");
    verify(entries).findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any()); verify(entries,never()).searchByUserAndTerm(any(),any());
  }

  @Test void resolvesLastWeekAsThePreviousCalendarWeek() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("show last week")).thenReturn(new JournalIntent(IntentType.QUERY_JOURNAL,null,null,null,null,null,null,null,List.of())); when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of());
    service.handle(1L,1L,"A","show last week");
    var start=org.mockito.ArgumentCaptor.forClass(Instant.class); var end=org.mockito.ArgumentCaptor.forClass(Instant.class); verify(entries).findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),start.capture(),end.capture()); ZoneId zone=ZoneId.of("Europe/Bucharest"); LocalDate weekStart=LocalDate.now(zone).minusDays(LocalDate.now(zone).getDayOfWeek().getValue()-1); assertThat(start.getValue()).isEqualTo(weekStart.minusWeeks(1).atStartOfDay(zone).toInstant()); assertThat(end.getValue()).isEqualTo(weekStart.atStartOfDay(zone).toInstant());
  }

  @Test void filtersACombinedFoodAndRomanianPeriodQuery() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    FoodEntry soup=new FoodEntry(user,"soup",Instant.now(),100,"manual","unknown"); FoodEntry pizza=new FoodEntry(user,"pizza",Instant.now(),200,"manual","unknown"); when(interpreter.interpret("arată supă ieri")).thenReturn(new JournalIntent(IntentType.QUERY_JOURNAL,null,null,"soup",null,null,null,null,List.of())); when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of(soup,pizza));
    String response=service.handle(1L,1L,"A","arată supă ieri");
    assertThat(response).contains("soup").doesNotContain("pizza"); verify(entries,never()).searchByUserAndTerm(any(),any());
  }

  @Test void editsOnlyAnEntryOwnedByTheRequestingUserAndRefreshesStatus() {
    FoodUser user = new FoodUser(1L, "A"); FoodEntry entry = new FoodEntry(user,"old",java.time.Instant.now(),100,"manual","unknown"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("correct entry 3")).thenReturn(new JournalIntent(IntentType.EDIT_ENTRY,"new",150,null,3L,null,null,null,List.of())); when(entries.findByIdAndUser(3L,user)).thenReturn(Optional.of(entry));
    assertThat(service.handle(1L,1L,"A","correct entry 3")).contains("Updated entry"); assertThat(entry.getOriginalMessage()).isEqualTo("new"); verify(dailyStatus).refresh(user,1L);
  }

  @Test void deletesOnlyTheRequestingUsersEntryAndDoesNotLeakItsExistence() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("delete entry 77")).thenReturn(new JournalIntent(IntentType.DELETE_ENTRY,null,null,null,77L,null,null,null,List.of())); when(entries.findByIdAndUser(77L,user)).thenReturn(Optional.empty());
    assertThat(service.handle(1L,1L,"A","delete entry 77")).isEqualTo("I could not find that entry."); verify(entries,never()).delete(any()); verify(dailyStatus,never()).refresh(any(),anyLong());
  }

  @Test void helpListsTheAvailableCommandsAndSafeExamples() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    String reply = service.handle(1L, 1L, "A", "/help");
    assertThat(reply).contains("/start", "/cancel", "/privacy", "kcal/100 g").doesNotContain("tool JSON");
    verifyNoInteractions(interpreter);
  }

  @Test void cancelClearsThePendingMealDraftAndAgentConfirmation() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    assertThat(service.handle(1L, 1L, "A", "/cancel")).contains("anulat");
    verify(drafts).deleteByUser(user);
    verify(pendingActions).deleteById(user.getId());
  }
}
