package io.github.foodjournal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.telegram.TelegramUpdate;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service @ConditionalOnProperty(prefix="food-journal",name="scheduling-enabled",havingValue="true",matchIfMissing=true)
public class TelegramInboxWorker {
 private final TelegramInboxClaimService claims; private final UpdateService updates; private final ObjectMapper json;
 public TelegramInboxWorker(TelegramInboxClaimService claims,UpdateService updates,ObjectMapper json){this.claims=claims;this.updates=updates;this.json=json;}
 @Scheduled(fixedDelayString="${food-journal.inbox-delay-ms:500}") public void dispatch(){TelegramInboxClaimService.Claim claim=claims.claim();if(claim==null)return;try{updates.processQueued(json.readValue(claim.payload(),TelegramUpdate.class),claim.updateId());claims.complete(claim.updateId(),claim.token());}catch(Exception failure){claims.retry(claim.updateId(),claim.token(),category(failure));}}
 private String category(Exception failure){return failure instanceof IllegalStateException?"TEMPORARY_FAILURE":"PROCESSING_FAILURE";}
}
