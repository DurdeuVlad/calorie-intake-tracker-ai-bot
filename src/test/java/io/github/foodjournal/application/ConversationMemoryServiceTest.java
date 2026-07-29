package io.github.foodjournal.application;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.ConversationMemoryRepository;
import io.github.foodjournal.repository.FoodUserRepository;
import java.util.*;
import org.junit.jupiter.api.Test;

class ConversationMemoryServiceTest {
  @Test void retainsOnlyTenMessagesForTheCurrentUser() {
    ConversationMemoryRepository repository = mock(ConversationMemoryRepository.class);
    FoodUserRepository users = mock(FoodUserRepository.class);
    FoodUser user = new FoodUser(1L, "Vlad");
    List<ConversationMemory> existing = new ArrayList<>();
    for (int i=0;i<12;i++) existing.add(new ConversationMemory(user, "user", "old-"+i));
    when(users.lockById(user.getId())).thenReturn(Optional.of(user));
    when(repository.findByUserOrderByCreatedAtDescIdDesc(user)).thenReturn(existing);
    new ConversationMemoryService(repository, users).recordTurn(user, "new user", "new assistant");
    verify(repository, times(2)).save(any(ConversationMemory.class));
    verify(repository).deleteAll(existing.subList(10, existing.size()));
  }
}
