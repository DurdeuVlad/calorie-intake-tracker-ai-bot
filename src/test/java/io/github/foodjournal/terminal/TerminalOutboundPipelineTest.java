package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import io.github.foodjournal.service.*;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TerminalOutboundPipelineTest {
  @Test void durableOutboxDeliveryKeepsItsSourceUpdateWhenRenderedLocally() throws Exception {
    OutboundTelegramClaimService claims=mock(OutboundTelegramClaimService.class); UUID token=UUID.randomUUID();
    when(claims.claimBatch()).thenReturn(List.of(new OutboundTelegramClaimService.Delivery(5L,42L,"Saved",9001L,token)));
    TerminalTelegramGateway terminal=new TerminalTelegramGateway();

    new OutboundTelegramDispatcher(claims,terminal).dispatch();

    assertThat(terminal.await(9001L,Duration.ofSeconds(1)).text()).isEqualTo("Saved");
    verify(claims).markSent(5L,token);
  }
}
