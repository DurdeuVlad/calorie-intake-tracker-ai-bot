package io.github.foodjournal.application;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.ConversationMemoryRepository;
import java.util.*;
import org.junit.jupiter.api.Test;

class ConversationMemoryServiceTest {
  @Test void retainsOnlyTenMessagesForTheCurrentUser() {
    ConversationMemoryRepository repository = mock(ConversationMemoryRepository.class);
    FoodUser user = new FoodUser(1L, "Vlad");
    List<ConversationMemory> existing = new ArrayList<>();
    for (int i=0;i<12;i++) existing.add(new ConversationMemory(user, "user", "old-"+i));
    when(repository.findByUserOrderByCreatedAtDesc(user)).thenReturn(existing);
    new ConversationMemoryService(repository).recordTurn(user, "new user", "new assistant");
    verify(repository, times(2)).save(any(ConversationMemory.class));
    verify(repository).deleteAll(existing.subList(10, existing.size()));
  }
}
