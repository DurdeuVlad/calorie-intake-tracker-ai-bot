package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Instant;
import java.util.*;
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
class JournalToolExecutorConfirmationPostgresTest {
  @Container static final PostgreSQLContainer<?> postgres=new PostgreSQLContainer<>("postgres:17-alpine");
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { registry.add("spring.datasource.url",postgres::getJdbcUrl); registry.add("spring.datasource.username",postgres::getUsername); registry.add("spring.datasource.password",postgres::getPassword); }
  @Autowired JournalToolExecutor tools; @Autowired FoodUserRepository users; @Autowired UserSettingsRepository settings; @Autowired FoodEntryRepository entries; @Autowired PendingAgentActionRepository pending;

  @Test @Transactional void batchDeleteIsImmediateReversibleAndTheActiveJournalHidesIt() {
    FoodUser user=users.save(new FoodUser(1,"Local")); settings.save(new UserSettings(user,"Europe/Bucharest"));
    FoodEntry entry=entries.save(new FoodEntry(user,"50 g crispy",Instant.now(),125,"manual","high"));
    AgentToolResult prepared=tools.execute(new AgentContext(user,1,true,"delete it",Instant.now()),new JournalAgentModel.ToolCall("apply","apply_journal_actions","{\"actions\":[{\"type\":\"DELETE\",\"entryId\":"+entry.getId()+"}]}"),new ArrayList<>());
    assertThat(prepared.ok()).isTrue();
    assertThat(entries.findById(entry.getId())).isPresent();
    assertThat(entries.findByIdAndUser(entry.getId(),user)).isEmpty();
    assertThat(pending.findById(user.getId())).isEmpty();
    AgentToolResult undone=tools.execute(new AgentContext(user,1,true,"undo",Instant.now()),new JournalAgentModel.ToolCall("undo","undo_last_change","{}"),new ArrayList<>());
    assertThat(undone.ok()).isTrue();
    assertThat(entries.findByIdAndUser(entry.getId(),user)).isPresent();
  }
}
