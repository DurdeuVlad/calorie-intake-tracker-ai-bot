package io.github.foodjournal.messaging;

import io.github.foodjournal.domain.*; import io.github.foodjournal.repository.*; import java.security.SecureRandom; import java.time.*; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;

@Service public class MessageLinkService {
 private static final char[] ALPHABET="ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray(); private final SecureRandom random=new SecureRandom();
 private final FrontendLinkCodeRepository codes; private final MessagingIdentityRepository identities; private final MessagingRouteRepository routes;
 public MessageLinkService(FrontendLinkCodeRepository codes,MessagingIdentityRepository identities,MessagingRouteRepository routes){this.codes=codes;this.identities=identities;this.routes=routes;}
 @Transactional public String issue(FoodUser user){String code;do{StringBuilder value=new StringBuilder(8);for(int i=0;i<8;i++)value.append(ALPHABET[random.nextInt(ALPHABET.length)]);code=value.toString();}while(codes.existsById(code));codes.save(new FrontendLinkCode(code,user,Instant.now().plus(Duration.ofMinutes(10))));return code;}
 @Transactional public FoodUser redeem(String code,String provider,String externalUserId,String conversationId){FrontendLinkCode link=codes.findById(code).filter(value->value.redeemable(Instant.now())).orElseThrow(()->new IllegalArgumentException("invalid or expired link code"));if(identities.findByProviderAndExternalUserId(provider,externalUserId).isPresent())throw new IllegalArgumentException("messaging account is already linked");FoodUser user=link.getUser();identities.save(new MessagingIdentity(user,provider,externalUserId));routes.findByUserAndProviderAndConversationId(user,provider,conversationId).orElseGet(()->routes.save(new MessagingRoute(user,provider,conversationId)));link.consume();return user;}
}
