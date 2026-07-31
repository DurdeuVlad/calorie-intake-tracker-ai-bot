package io.github.foodjournal.repository;
import io.github.foodjournal.domain.FoodItem; import org.springframework.data.jpa.repository.JpaRepository;
public interface FoodItemRepository extends JpaRepository<FoodItem,Long>{ void deleteByEntry(io.github.foodjournal.domain.FoodEntry entry); }
