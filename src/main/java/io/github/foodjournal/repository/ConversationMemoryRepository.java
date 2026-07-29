package io.github.foodjournal.repository;

import io.github.foodjournal.domain.*;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConversationMemoryRepository extends JpaRepository<ConversationMemory,Long> {
 List<ConversationMemory> findTop10ByUserOrderByCreatedAtDesc(FoodUser user);
 List<ConversationMemory> findByUserOrderByCreatedAtDesc(FoodUser user);
}
