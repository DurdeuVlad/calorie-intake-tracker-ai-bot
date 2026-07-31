package io.github.foodjournal.repository;
import io.github.foodjournal.domain.FoodEntry; import io.github.foodjournal.domain.FoodUser; import java.time.*; import java.util.List; import org.springframework.data.jpa.repository.JpaRepository;
public interface FoodEntryRepository extends JpaRepository<FoodEntry,Long>{
 @org.springframework.data.jpa.repository.Query("select e from FoodEntry e where e.user = :user and e.deletedAt is null and e.eatenAt >= :start and e.eatenAt < :end order by e.eatenAt asc") List<FoodEntry> findByUserAndEatenAtBetweenOrderByEatenAtAsc(FoodUser user, Instant start, Instant end);
 @org.springframework.data.jpa.repository.Query("select e from FoodEntry e where e.id = :id and e.user = :user and e.deletedAt is null") java.util.Optional<FoodEntry> findByIdAndUser(Long id, FoodUser user);
 @org.springframework.data.jpa.repository.Query("select e from FoodEntry e where e.id = :id and e.user = :user") java.util.Optional<FoodEntry> findIncludingDeletedByIdAndUser(Long id, FoodUser user);
 @org.springframework.data.jpa.repository.Query("select count(e) from FoodEntry e where e.user = :user and e.deletedAt is null") long countByUser(FoodUser user);
 @org.springframework.data.jpa.repository.Query("select e from FoodEntry e where e.user = :user and e.deletedAt is null and lower(e.originalMessage) like lower(concat('%', :term, '%')) order by e.eatenAt desc") List<FoodEntry> searchByUserAndTerm(FoodUser user, String term);
 @org.springframework.data.jpa.repository.Query("select e from FoodEntry e where e.user = :user and e.deletedAt is null and e.confidence = 'estimate' order by e.eatenAt desc") List<FoodEntry> findEstimatedByUserOrderByEatenAtDesc(FoodUser user);
}
