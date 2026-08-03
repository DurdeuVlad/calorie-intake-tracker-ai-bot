package io.github.foodjournal.repository;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.domain.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=1","food-journal.scheduling-enabled=false"})
@Testcontainers(disabledWithoutDocker=true)
class JournalChangeSetRepositoryPostgresTest {
  @Container static final PostgreSQLContainer<?> POSTGRES=new PostgreSQLContainer<>("postgres:17-alpine");
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry){registry.add("spring.datasource.url",POSTGRES::getJdbcUrl);registry.add("spring.datasource.username",POSTGRES::getUsername);registry.add("spring.datasource.password",POSTGRES::getPassword);}
  @Autowired FoodUserRepository users; @Autowired FoodEntryRepository entries; @Autowired FoodItemRepository items; @Autowired JournalChangeSetRepository changeSets;

  @Test @Transactional void persistsOrderedSnapshotsAndSelectsLatestUnexpiredBatch(){
    Instant now=Instant.parse("2026-08-02T10:00:00Z");FoodUser user=users.save(new FoodUser(99881,"Undo test"));
    FoodEntry entry=entries.save(new FoodEntry(user,"salad",now.minusSeconds(60),300,"manual","high"));
    FoodItem item=items.save(new FoodItem(entry,"salad",BigDecimal.ONE,QuantityUnit.PORTION,300,null,null,null,"manual","high"));
    JournalEntrySnapshot before=JournalEntrySnapshot.capture(entry,List.of(item));entry.moveTo(now.minusSeconds(3600));
    JournalEntrySnapshot after=JournalEntrySnapshot.capture(entry,List.of(item));
    JournalChangeSet older=JournalChangeSet.start(user,now.minusSeconds(120));older.addMutation(JournalMutationType.MOVE,before,after);changeSets.saveAndFlush(older);
    JournalChangeSet latest=JournalChangeSet.start(user,now);latest.addMutation(JournalMutationType.DELETE,after,null);latest.addMutation(JournalMutationType.CREATE,null,after);changeSets.saveAndFlush(latest);
    JournalChangeSet loaded=changeSets.findFirstByUserAndUndoneAtIsNullAndExpiresAtAfterOrderByCreatedAtDescIdDesc(user,now.plusSeconds(1)).orElseThrow();
    assertThat(loaded.getId()).isEqualTo(latest.getId());assertThat(loaded.getMutations()).extracting(JournalMutation::getActionType).containsExactly(JournalMutationType.DELETE,JournalMutationType.CREATE);
    assertThat(loaded.getMutations().getFirst().getBeforeState().items().getFirst().quantityUnit()).isEqualTo(QuantityUnit.PORTION);
  }
}
