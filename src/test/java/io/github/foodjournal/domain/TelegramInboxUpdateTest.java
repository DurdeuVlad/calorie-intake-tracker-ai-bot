package io.github.foodjournal.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import org.junit.jupiter.api.Test;

class TelegramInboxUpdateTest {
  @Test void discardsPrivatePayloadAfterSuccessfulProcessing(){TelegramInboxUpdate update=new TelegramInboxUpdate(1,2,3,"private text");update.claim();update.complete(update.getLeaseToken());assertThat(update.getPayload()).isEmpty();assertThat(update.getStatus()).isEqualTo(TelegramInboxUpdate.Status.COMPLETED);}
  @Test void discardsPrivatePayloadAfterFinalFailure(){TelegramInboxUpdate update=new TelegramInboxUpdate(1,2,3,"private text");for(int i=0;i<3;i++){update.claim();UUID token=update.getLeaseToken();update.retry(token,"TEMPORARY_FAILURE");}assertThat(update.getPayload()).isEmpty();assertThat(update.getStatus()).isEqualTo(TelegramInboxUpdate.Status.FAILED);assertThat(update.getLastErrorCategory()).isEqualTo("TEMPORARY_FAILURE");}
}
