package io.github.foodjournal.repository;
import io.github.foodjournal.domain.MessagingOutboundMessage; import java.util.*; import org.springframework.data.jpa.repository.*;
public interface MessagingOutboundRepository extends JpaRepository<MessagingOutboundMessage,Long>{ @Query(value="select * from messaging_outbox where status='PENDING' or (status='IN_PROGRESS' and lease_expires_at <= current_timestamp) order by id limit 10 for update skip locked",nativeQuery=true) List<MessagingOutboundMessage> lockReady(); }
