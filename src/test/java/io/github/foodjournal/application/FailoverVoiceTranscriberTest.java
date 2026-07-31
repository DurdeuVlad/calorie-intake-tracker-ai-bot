package io.github.foodjournal.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

class FailoverVoiceTranscriberTest {
  @Test void usesOpenAiAfterEligibleGeminiFailureAndDownloadsOnlyOnce() {
    byte[] bytes={1,2,3}; int[] downloads={0};
    VoiceTranscriptionProvider gemini=provider("gemini", value -> { throw new MediaProcessingException(MediaProcessingException.Category.PROVIDER_TEMPORARY,"down"); });
    VoiceTranscriptionProvider openai=provider("openai", value -> "two eggs");
    String transcript=new FailoverVoiceTranscriber(id->{downloads[0]++;return new TransientVoicePayload(bytes);},gemini,openai,new SimpleMeterRegistry()).transcribe("voice","audio/ogg");
    assertThat(transcript).isEqualTo("two eggs"); assertThat(downloads[0]).isEqualTo(1); assertThat(bytes).containsOnly((byte)0);
  }
  @Test void doesNotCallProvidersForInvalidMedia() {
    VoiceTranscriptionProvider provider=provider("x", bytes -> { throw new AssertionError("must not run"); });
    assertThatThrownBy(()->new FailoverVoiceTranscriber(id->new TransientVoicePayload(new byte[0]),provider,provider,new SimpleMeterRegistry()).transcribe("voice","audio/ogg"))
        .isInstanceOfSatisfying(MediaProcessingException.class,f->assertThat(f.category()).isEqualTo(MediaProcessingException.Category.INVALID_MEDIA));
  }
  @Test void preservesBothFailureAndErasesMedia() {
    byte[] bytes={1,2,3}; VoiceTranscriptionProvider gemini=provider("gemini", value->{throw new MediaProcessingException(MediaProcessingException.Category.RATE_LIMITED,"limited");}); VoiceTranscriptionProvider openai=provider("openai", value->{throw new MediaProcessingException(MediaProcessingException.Category.PROVIDER_TEMPORARY,"down");});
    assertThatThrownBy(()->new FailoverVoiceTranscriber(id->new TransientVoicePayload(bytes),gemini,openai,new SimpleMeterRegistry()).transcribe("voice","audio/ogg")).isInstanceOf(MediaProcessingException.class); assertThat(bytes).containsOnly((byte)0);
  }
  @Test void fallsBackOnlyForProviderFailures() {
    assertThat(FailoverVoiceTranscriber.fallbackEligible(new MediaProcessingException(MediaProcessingException.Category.NOT_CONFIGURED,"x"))).isTrue();
    assertThat(FailoverVoiceTranscriber.fallbackEligible(new MediaProcessingException(MediaProcessingException.Category.MODEL_UNAVAILABLE,"x"))).isTrue();
    assertThat(FailoverVoiceTranscriber.fallbackEligible(new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"x"))).isFalse();
    assertThat(FailoverVoiceTranscriber.fallbackEligible(new MediaProcessingException(MediaProcessingException.Category.INVALID_MEDIA,"x"))).isFalse();
  }
  private VoiceTranscriptionProvider provider(String name, java.util.function.Function<byte[],String> behavior){return new VoiceTranscriptionProvider(){public String name(){return name;}public String transcribe(byte[] bytes,String mime){return behavior.apply(bytes);}};}
}
