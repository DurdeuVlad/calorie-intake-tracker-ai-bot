package io.github.foodjournal.infrastructure.openfoodfacts;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.application.NutritionProfile;
import io.github.foodjournal.config.BotProperties;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component public class OpenFoodFactsClient {
 private final RestClient client;
 @Autowired public OpenFoodFactsClient(RestClient.Builder builder,BotProperties properties){this(builder.baseUrl(properties.openFoodFactsBaseUrl()).build());}
 OpenFoodFactsClient(RestClient client){this.client=client;}
 public Optional<NutritionProfile> byBarcode(String barcode){if(barcode==null||!barcode.matches("\\d{8,14}"))return Optional.empty();try{JsonNode response=client.get().uri(uri->uri.path("/product/{barcode}").queryParam("fields","code,product_name,nutriments").build(barcode)).retrieve().body(JsonNode.class);JsonNode product=response==null?null:response.path("product");JsonNode nutrients=product==null?null:product.path("nutriments");if(response==null||response.path("status").asInt()!=1||product==null||product.path("product_name").asText().isBlank())return Optional.empty();Integer calories=integer(nutrients,"energy-kcal_100g");if(calories==null)return Optional.empty();return Optional.of(new NutritionProfile(product.path("product_name").asText(),calories,number(nutrients,"proteins_100g"),number(nutrients,"carbohydrates_100g"),number(nutrients,"fat_100g"),"open_food_facts","https://world.openfoodfacts.org/product/"+barcode));}catch(Exception ignored){return Optional.empty();}}
 public List<PackagedFoodResult> searchByName(String name,String brand){if(blank(name))return List.of();try{String terms=blank(brand)?name:name+" "+brand;JsonNode response=client.get().uri(uri->uri.path("/search").queryParam("search_terms",terms).queryParam("fields","code,product_name,brands,nutriments").queryParam("page_size",20).build()).retrieve().body(JsonNode.class);JsonNode products=response==null?null:response.path("products");if(products==null||!products.isArray())return List.of();List<RankedResult> matches=new ArrayList<>();int sourceOrder=0;for(JsonNode product:products){String barcode=product.path("code").asText();String productName=product.path("product_name").asText().trim();String productBrand=product.path("brands").asText().trim();Integer calories=integer(product.path("nutriments"),"energy-kcal_100g");if(!barcode.matches("\\d{8,14}")||productName.isBlank()||calories==null||calories<1||calories>2000){sourceOrder++;continue;}int exact=exactMatch(name,brand,productName,productBrand)?1:0;int overlap=tokenOverlap(terms,productName+" "+productBrand);matches.add(new RankedResult(new PackagedFoodResult(productName,productBrand,calories,barcode,"https://world.openfoodfacts.org/product/"+barcode,exact==1?"EXACT":"PARTIAL"),exact,overlap,sourceOrder++));}return matches.stream().sorted(Comparator.comparingInt(RankedResult::exact).reversed().thenComparing(Comparator.comparingInt(RankedResult::overlap).reversed()).thenComparingInt(RankedResult::sourceOrder)).limit(5).map(RankedResult::result).toList();}catch(Exception ignored){return List.of();}}
 public record PackagedFoodResult(String productName,String brand,int caloriesPer100g,String barcode,String sourceUrl,String matchQuality) {}
 private record RankedResult(PackagedFoodResult result,int exact,int overlap,int sourceOrder) {}
 private boolean exactMatch(String name,String requestedBrand,String productName,String productBrand){return normalized(name).equals(normalized(productName))||(!blank(requestedBrand)&&normalized(requestedBrand).equals(normalized(productBrand)));}
 private int tokenOverlap(String query,String candidate){List<String> queryTokens=List.of(normalized(query).split(" "));String normalizedCandidate=normalized(candidate);return (int)queryTokens.stream().filter(token->!token.isBlank()&&normalizedCandidate.contains(token)).count();}
 private boolean blank(String value){return value==null||value.isBlank();}
 private String normalized(String value){return Normalizer.normalize(value==null?"":value,Normalizer.Form.NFD).replaceAll("\\p{M}","").toLowerCase().replaceAll("[^a-z0-9]+"," ").trim();}
 private Integer integer(JsonNode root,String field){Double number=number(root,field);return number==null?null:(int)Math.round(number);}
 private Double number(JsonNode root,String field){return root==null||!root.path(field).isNumber()?null:root.path(field).asDouble();}
}
