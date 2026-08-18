package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.messaging.InboundMessage;
import io.github.foodjournal.messaging.MessagingDispatcher;
import io.github.foodjournal.messaging.MessagingIngressService;
import io.github.foodjournal.messaging.MessagingInboxWorker;
import java.time.Duration;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class TerminalConversationTest {
  @Test void wrapsTerminalTextInAnAllowlistedSyntheticMessage() throws Exception {
    MessagingIngressService ingress=mock(MessagingIngressService.class); MessagingInboxWorker inbox=mock(MessagingInboxWorker.class); MessagingDispatcher outbox=mock(MessagingDispatcher.class); TerminalFrontend frontend=new TerminalFrontend();
    doAnswer(call->{frontend.send("42","Saved."); return null;}).when(outbox).dispatch();
    TerminalConversation chat=new TerminalConversation(ingress,inbox,outbox,frontend,new TerminalTraceCollector(),new TerminalProperties(42,"Local",null,null),props(42));

    TerminalConversation.Result result=chat.send("two eggs");

    ArgumentCaptor<InboundMessage> captured=ArgumentCaptor.forClass(InboundMessage.class);
    verify(ingress).accept(captured.capture());
    assertThat(captured.getValue().provider()).isEqualTo("terminal");
    assertThat(captured.getValue().text()).isEqualTo("two eggs");
    assertThat(captured.getValue().userId()).isEqualTo("42");
    assertThat(result.reply()).isEqualTo("Saved.");
  }

  @Test void rejectsATerminalUserOutsideTheTelegramAllowlist() {
    assertThatThrownBy(()->new TerminalConversation(mock(MessagingIngressService.class),mock(MessagingInboxWorker.class),mock(MessagingDispatcher.class),new TerminalFrontend(),new TerminalTraceCollector(),new TerminalProperties(42,"Local",null,null),props(7))).isInstanceOf(IllegalStateException.class).hasMessageContaining("ALLOWED_TELEGRAM_USER_IDS");
  }

  @Test void resetDiscardsAStaleQueuedDeliveryBeforeTheNextSend() throws Exception {
    TerminalFrontend frontend=new TerminalFrontend();
    frontend.send("42","stale reply from a previous turn");

    frontend.reset();

    assertThat(frontend.awaitReply(Duration.ofMillis(50))).isNull();
  }

  private BotProperties props(long user) { return new BotProperties("token","secret",Set.of(user),"Europe/Bucharest","key","test"); }
}
