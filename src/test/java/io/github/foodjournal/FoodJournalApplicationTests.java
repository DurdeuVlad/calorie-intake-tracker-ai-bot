package io.github.foodjournal;
import org.junit.jupiter.api.Test; import org.springframework.boot.test.context.SpringBootTest;
@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=1","spring.datasource.url=jdbc:h2:mem:test;MODE=PostgreSQL;DB_CLOSE_DELAY=-1","spring.jpa.hibernate.ddl-auto=none","spring.flyway.enabled=false","food-journal.scheduling-enabled=false"}) class FoodJournalApplicationTests { @Test void contextLoads(){} }
