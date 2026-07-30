package io.github.foodjournal.service;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.telegram.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TelegramInboxWorkerTest {
  @Test void processesClaimedUpdateInTheAtomicCompletionTransaction(){TelegramInboxClaimService claims=mock(TelegramInboxClaimService.class);UpdateService updates=mock(UpdateService.class);TelegramUpdate update=new TelegramUpdate(17L,new TelegramMessage(1L,new TelegramChat(2L),new TelegramUser(3L,"Vlad"),"hello",null,null,null),null);String payload=toJson(update);UUID token=UUID.randomUUID();when(claims.claim()).thenReturn(new TelegramInboxClaimService.Claim(17L,payload,token));new TelegramInboxWorker(claims,updates,new ObjectMapper()).dispatch();verify(updates).processQueued(any(TelegramUpdate.class),eq(17L),eq(token));verify(claims,never()).complete(anyLong(),any());verify(claims,never()).retry(anyLong(),any(),anyString());}
  @Test void retriesWhenAtomicProcessingFails(){TelegramInboxClaimService claims=mock(TelegramInboxClaimService.class);UpdateService updates=mock(UpdateService.class);UUID token=UUID.randomUUID();when(claims.claim()).thenReturn(new TelegramInboxClaimService.Claim(18L,toJson(new TelegramUpdate(18L,null,null)),token));doThrow(new IllegalStateException("provider")).when(updates).processQueued(any(),eq(18L),eq(token));new TelegramInboxWorker(claims,updates,new ObjectMapper()).dispatch();verify(claims).retry(18L,token,"TEMPORARY_FAILURE");}
  private static String toJson(TelegramUpdate update){try{return new ObjectMapper().writeValueAsString(update);}catch(Exception e){throw new RuntimeException(e);}}
}
