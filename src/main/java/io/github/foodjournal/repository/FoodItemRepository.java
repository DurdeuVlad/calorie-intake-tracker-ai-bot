package io.github.foodjournal.repository;
import io.github.foodjournal.domain.FoodEntry; import io.github.foodjournal.domain.FoodItem; import java.util.List; import org.springframework.data.jpa.repository.JpaRepository; import org.springframework.data.jpa.repository.Query;
public interface FoodItemRepository extends JpaRepository<FoodItem,Long>{ @Query("select i from FoodItem i where i.entry = :entry order by i.id") List<FoodItem> findByEntry(FoodEntry entry); void deleteByEntry(FoodEntry entry); }
