package io.github.foodjournal.service;

import io.github.foodjournal.domain.TelegramInboxUpdate;
import io.github.foodjournal.repository.TelegramInboxUpdateRepository;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service public class TelegramInboxClaimService {
 private final TelegramInboxUpdateRepository inbox;
 public TelegramInboxClaimService(TelegramInboxUpdateRepository inbox){this.inbox=inbox;}
 @Transactional public Claim claim(){return inbox.lockNextReady().stream().findFirst().map(row->{row.claim();return new Claim(row.getUpdateId(),row.getPayload(),row.getLeaseToken());}).orElse(null);}
 @Transactional public void complete(long id,UUID token){inbox.findById(id).ifPresent(row->row.complete(token));}
 @Transactional public void retry(long id,UUID token,String category){inbox.findById(id).ifPresent(row->row.retry(token,category));}
 public record Claim(long updateId,String payload,UUID token) {}
}
