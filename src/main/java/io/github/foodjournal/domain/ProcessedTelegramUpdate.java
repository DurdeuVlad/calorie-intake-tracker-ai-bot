package io.github.foodjournal.domain;
import jakarta.persistence.*;
import java.time.Instant;
@Entity @Table(name="processed_telegram_updates")
public class ProcessedTelegramUpdate {
 @Id private Long updateId; @Column(nullable=false) private Instant processedAt=Instant.now(); protected ProcessedTelegramUpdate(){} public ProcessedTelegramUpdate(long id){this.updateId=id;}
}
