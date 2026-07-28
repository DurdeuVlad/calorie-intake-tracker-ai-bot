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
import io.github.foodjournal.domain.FoodItem;
import io.github.foodjournal.application.DailyStatusService;
import java.util.List;
import java.util.Optional; import java.util.Set;
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
  private JournalApplicationService service;

  @BeforeEach void setUp() { service = new JournalApplicationService(users, settings, entries, items, privateFoods, interpreter, new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), dailyStatus, NutritionResolver.noop()); }
  private void configured(FoodUser user){UserSettings value=new UserSettings(user,"Europe/Bucharest");value.completeOnboarding();when(settings.findById(user.getId())).thenReturn(Optional.of(value));}

  @Test void rejectsInvalidCaloriesWithoutWriting() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    configured(user);
    when(interpreter.interpret("huge meal")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "huge meal", 10001, null, null, null, null, null, List.of()));

    assertThat(service.handle(1L, 1L, "A", "huge meal")).contains("not valid");
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

    assertThat(service.handle(1L, 1L, "A", "I ate soup")).startsWith("Logged: vegetable soup");
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

    assertThat(service.handleMediaEvidence(1L, 1L, "A", "Oat bar, 180 kcal")).contains("estimates");

    verify(entries).save(argThat(entry -> entry.getNutritionSource().equals("ai_estimate") && entry.getConfidence().equals("estimate")));
  }

  @Test void savesAHouseholdFoodForOnlyTheRequestingUser() {
    FoodUser user = new FoodUser(1L, "A"); when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user)); configured(user);
    when(interpreter.interpret("save grandma soup")).thenReturn(new JournalIntent(IntentType.SAVE_PRIVATE_FOOD,"grandma soup",null,null,null,null,null,null,List.of(new JournalIntent.MealItem("Grandma soup",100d,80,4d,10d,2d))));
    assertThat(service.handle(1L,1L,"A","save grandma soup")).isEqualTo("Saved household food: Grandma soup.");
    verify(privateFoods).save(argThat(food->food.getName().equals("Grandma soup")&&food.getCaloriesPer100g()==80));
  }
}
