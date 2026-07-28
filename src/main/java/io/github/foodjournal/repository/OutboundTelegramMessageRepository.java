package io.github.foodjournal.repository;
import io.github.foodjournal.domain.OutboundTelegramMessage; import java.time.Instant; import java.util.List; import org.springframework.data.jpa.repository.JpaRepository;
public interface OutboundTelegramMessageRepository extends JpaRepository<OutboundTelegramMessage,Long>{
  List<OutboundTelegramMessage> findByStatusAndNextAttemptAtLessThanEqualOrderById(OutboundTelegramMessage.Status status, Instant now, org.springframework.data.domain.Pageable pageable);
}
