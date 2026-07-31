package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.service.UpdateService;
import io.github.foodjournal.service.TelegramInboxWorker;
import io.github.foodjournal.service.OutboundTelegramDispatcher;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class TerminalConversationTest {
  @Test void wrapsTerminalTextInAnAllowlistedSyntheticTelegramUpdate() throws Exception {
    UpdateService updates=mock(UpdateService.class); TelegramInboxWorker inbox=mock(TelegramInboxWorker.class); OutboundTelegramDispatcher outbox=mock(OutboundTelegramDispatcher.class); TerminalTelegramGateway gateway=new TerminalTelegramGateway(); AtomicLong updateId=new AtomicLong();
    doAnswer(call->{updateId.set(call.<io.github.foodjournal.telegram.TelegramUpdate>getArgument(0).update_id());return null;}).when(updates).enqueue(any());
    doAnswer(call->{gateway.sendTerminalMessage(42,"Saved.",updateId.get());return null;}).when(outbox).dispatch();
    TerminalConversation chat=new TerminalConversation(updates,inbox,outbox,gateway,new TerminalTraceCollector(),new TerminalProperties(42,"Local",null,null),props(42));

    TerminalConversation.Result result=chat.send("two eggs");

    ArgumentCaptor<io.github.foodjournal.telegram.TelegramUpdate> captured=ArgumentCaptor.forClass(io.github.foodjournal.telegram.TelegramUpdate.class);
    verify(updates).enqueue(captured.capture());
    assertThat(captured.getValue().message().text()).isEqualTo("two eggs");
    assertThat(captured.getValue().message().from().id()).isEqualTo(42L);
    assertThat(result.reply()).isEqualTo("Saved.");
  }

  @Test void rejectsATerminalUserOutsideTheTelegramAllowlist() {
    assertThatThrownBy(()->new TerminalConversation(mock(UpdateService.class),mock(TelegramInboxWorker.class),mock(OutboundTelegramDispatcher.class),new TerminalTelegramGateway(),new TerminalTraceCollector(),new TerminalProperties(42,"Local",null,null),props(7))).isInstanceOf(IllegalStateException.class).hasMessageContaining("ALLOWED_TELEGRAM_USER_IDS");
  }

  @Test void deliversRepliesToTheirMatchingSyntheticUpdateWhenAnOlderDeliveryIsQueued() throws Exception {
    TerminalTelegramGateway gateway=new TerminalTelegramGateway();
    gateway.sendTerminalMessage(42,"older",100L); gateway.sendTerminalMessage(42,"current",200L);

    assertThat(gateway.await(200L,java.time.Duration.ofSeconds(1)).text()).isEqualTo("current");
    assertThat(gateway.await(100L,java.time.Duration.ofSeconds(1)).text()).isEqualTo("older");
  }

  private BotProperties props(long user) { return new BotProperties("token","secret",Set.of(user),"Europe/Bucharest","key","test"); }
}
