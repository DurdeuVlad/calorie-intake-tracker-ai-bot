package io.github.foodjournal.infrastructure.openfoodfacts;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.application.NutritionProfile;
import io.github.foodjournal.config.BotProperties;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component public class OpenFoodFactsClient {
 private final RestClient client;
 @Autowired public OpenFoodFactsClient(RestClient.Builder builder,BotProperties properties){this(builder.baseUrl(properties.openFoodFactsBaseUrl()).build());}
 OpenFoodFactsClient(RestClient client){this.client=client;}
 public Optional<NutritionProfile> byBarcode(String barcode){if(barcode==null||!barcode.matches("\\d{8,14}"))return Optional.empty();try{JsonNode response=client.get().uri(uri->uri.path("/product/{barcode}").queryParam("fields","code,product_name,nutriments").build(barcode)).retrieve().body(JsonNode.class);JsonNode product=response==null?null:response.path("product");JsonNode nutrients=product==null?null:product.path("nutriments");if(response==null||response.path("status").asInt()!=1||product==null||product.path("product_name").asText().isBlank())return Optional.empty();Integer calories=integer(nutrients,"energy-kcal_100g");if(calories==null)return Optional.empty();return Optional.of(new NutritionProfile(product.path("product_name").asText(),calories,number(nutrients,"proteins_100g"),number(nutrients,"carbohydrates_100g"),number(nutrients,"fat_100g"),"open_food_facts","https://world.openfoodfacts.org/product/"+barcode));}catch(Exception ignored){return Optional.empty();}}
 private Integer integer(JsonNode root,String field){Double number=number(root,field);return number==null?null:(int)Math.round(number);}
 private Double number(JsonNode root,String field){return root==null||!root.path(field).isNumber()?null:root.path(field).asDouble();}
}
