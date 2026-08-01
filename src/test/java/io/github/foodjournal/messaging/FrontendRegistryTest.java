package io.github.foodjournal.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import io.github.foodjournal.application.TransientVoicePayload;
import java.util.List;
import org.junit.jupiter.api.Test;

class FrontendRegistryTest {
  @Test void resolvesOnlyEnabledProviderAndAppliesItsTextLimit() {
    MessagingFrontend enabled = new Stub("mattermost", true, 30);
    MessagingFrontend disabled = new Stub("telegram", false, 4);
    FrontendRegistry registry = new FrontendRegistry(List.of(enabled, disabled));
    assertThat(registry.find("mattermost")).contains(enabled);
    assertThat(registry.find("telegram")).isEmpty();
    assertThat(MessagingDispatcher.fit("a".repeat(40), 30)).hasSize(30).endsWith("[Message truncated]");
  }
  private record Stub(String provider, boolean enabled, int messageLimit) implements MessagingFrontend {
    public String send(String conversationId,String text){return "post";} public void edit(String conversationId,String messageId,String text){} public TransientVoicePayload download(Attachment attachment){return new TransientVoicePayload(new byte[0]);}
  }
}
