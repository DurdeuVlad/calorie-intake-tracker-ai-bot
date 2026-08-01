package io.github.foodjournal.repository;
import io.github.foodjournal.domain.MessagingInboxMessage; import java.util.*; import org.springframework.data.jpa.repository.*;
public interface MessagingInboxRepository extends JpaRepository<MessagingInboxMessage,Long>{ @Query(value="select * from messaging_inbox where status='PENDING' or (status='IN_PROGRESS' and lease_expires_at <= current_timestamp) order by id for update skip locked limit 1",nativeQuery=true) List<MessagingInboxMessage> lockReady(); }
