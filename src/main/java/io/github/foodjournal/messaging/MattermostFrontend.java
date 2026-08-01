package io.github.foodjournal.messaging;

import io.github.foodjournal.application.*;
import io.github.foodjournal.config.MessagingProperties;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Mattermost REST transport; inbound posts are fed by MattermostWebSocketListener. */
@Component
@ConditionalOnProperty(prefix="food-journal.frontends.mattermost", name="enabled", havingValue="true")
public class MattermostFrontend implements MessagingFrontend {
 private final RestClient api; private final MessagingProperties.Mattermost config;
 public MattermostFrontend(RestClient.Builder builder,MessagingProperties properties){config=properties.mattermost();api=builder.baseUrl(config.internalUrl()).defaultHeader(HttpHeaders.AUTHORIZATION,"Bearer "+config.botToken()).build();}
 public String provider(){return "mattermost";} public boolean enabled(){return !config.internalUrl().isBlank()&&!config.botToken().isBlank()&&!config.botUserId().isBlank();} public int messageLimit(){return 16000;}
 public String send(String conversationId,String text){Map<?,?> post=api.post().uri("/api/v4/posts").body(Map.of("channel_id",conversationId,"message",text)).retrieve().body(Map.class);Object id=post==null?null:post.get("id");if(id==null)throw new IllegalStateException("Mattermost delivery failed");return String.valueOf(id);}
 public void edit(String conversationId,String messageId,String text){api.put().uri("/api/v4/posts/{id}",messageId).body(Map.of("id",messageId,"channel_id",conversationId,"message",text)).retrieve().toBodilessEntity();}
 public TransientVoicePayload download(Attachment attachment){try{byte[] bytes=api.get().uri("/api/v4/files/{id}",attachment.handle()).retrieve().body(byte[].class);if(bytes==null)throw new IllegalStateException("media unavailable");return new TransientVoicePayload(bytes);}catch(RuntimeException failure){throw new MediaProcessingException(MediaProcessingException.Category.TELEGRAM_DOWNLOAD,"Messaging media download failed",failure);}}
 public Attachment attachment(String fileId){Map<?,?> info=api.get().uri("/api/v4/files/{id}/info",fileId).retrieve().body(Map.class);Object mimeValue=info==null?null:info.get("mime_type");Object nameValue=info==null?null:info.get("name");String mime=mimeValue==null?"application/octet-stream":String.valueOf(mimeValue);String name=nameValue==null?null:String.valueOf(nameValue);Attachment.Kind kind=mime.startsWith("image/")?Attachment.Kind.PHOTO:mime.startsWith("audio/")?Attachment.Kind.VOICE:Attachment.Kind.DOCUMENT;return new Attachment(kind,fileId,mime,name);}
 public String directChannel(String userId){Map<?,?> channel=api.post().uri("/api/v4/channels/direct").body(List.of(config.botUserId(),userId)).retrieve().body(Map.class);Object id=channel==null?null:channel.get("id");if(id==null)throw new IllegalStateException("Mattermost direct channel failed");return String.valueOf(id);}
}
