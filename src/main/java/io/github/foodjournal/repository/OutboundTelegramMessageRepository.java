package io.github.foodjournal.repository;
import io.github.foodjournal.domain.OutboundTelegramMessage; import java.util.List; import org.springframework.data.jpa.repository.*;
public interface OutboundTelegramMessageRepository extends JpaRepository<OutboundTelegramMessage,Long>{
  @Query(value="select * from outbound_telegram_messages where (status = 'PENDING' and next_attempt_at <= current_timestamp) or (status = 'IN_PROGRESS' and lease_expires_at <= current_timestamp) order by id limit 50 for update skip locked", nativeQuery=true)
  List<OutboundTelegramMessage> lockReadyForDelivery();
}
