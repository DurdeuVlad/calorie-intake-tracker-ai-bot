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
  @Mock IntentInterpreter interpreter;
  private JournalApplicationService service;

  @BeforeEach void setUp() { service = new JournalApplicationService(users, settings, entries, interpreter, new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test")); }

  @Test void rejectsInvalidCaloriesWithoutWriting() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    when(interpreter.interpret("huge meal")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "huge meal", 10001, null, null, null, null, List.of()));

    assertThat(service.handle(1L, "A", "huge meal")).contains("not valid");
    verify(entries, never()).save(any());
  }

  @Test void cannotDeleteAnotherUsersEntry() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    when(interpreter.interpret("delete 99")).thenReturn(new JournalIntent(IntentType.DELETE_ENTRY, null, null, null, 99L, null, null, List.of()));
    when(entries.findByIdAndUser(99L, user)).thenReturn(Optional.empty());

    assertThat(service.handle(1L, "A", "delete 99")).contains("could not find");
    verify(entries, never()).delete(any());
  }

  @Test void persistsValidMealForTheRequestingUserOnly() {
    FoodUser user = new FoodUser(1L, "A");
    when(users.findByTelegramUserId(1L)).thenReturn(Optional.of(user));
    when(interpreter.interpret("I ate soup")).thenReturn(new JournalIntent(IntentType.LOG_MEAL, "vegetable soup", 220, null, null, null, null, List.of()));
    when(entries.save(any(FoodEntry.class))).thenAnswer(invocation -> invocation.getArgument(0));

    assertThat(service.handle(1L, "A", "I ate soup")).startsWith("Logged: vegetable soup");
    verify(entries).save(argThat(entry -> entry.getUser() == user && entry.getCalories() == 220));
  }
}
