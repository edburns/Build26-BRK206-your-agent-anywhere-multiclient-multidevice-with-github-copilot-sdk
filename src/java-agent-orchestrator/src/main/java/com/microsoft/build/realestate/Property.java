package com.microsoft.build.realestate;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * JPA entity representing a real-estate property listing.
 */
@Entity
@Table(name = "PROPERTY")
public class Property {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    private String type;
    private String city;
    private String neighbourhood;
    private int bedrooms;
    private double priceGbp;
    private String description;

    public Property() {}

    public Property(String type, String city, String neighbourhood,
                    int bedrooms, double priceGbp, String description) {
        this.type = type;
        this.city = city;
        this.neighbourhood = neighbourhood;
        this.bedrooms = bedrooms;
        this.priceGbp = priceGbp;
        this.description = description;
    }

    public Long getId() { return id; }
    public String getType() { return type; }
    public String getCity() { return city; }
    public String getNeighbourhood() { return neighbourhood; }
    public int getBedrooms() { return bedrooms; }
    public double getPriceGbp() { return priceGbp; }
    public String getDescription() { return description; }

    public void setType(String type) { this.type = type; }
    public void setCity(String city) { this.city = city; }
    public void setNeighbourhood(String neighbourhood) { this.neighbourhood = neighbourhood; }
    public void setBedrooms(int bedrooms) { this.bedrooms = bedrooms; }
    public void setPriceGbp(double priceGbp) { this.priceGbp = priceGbp; }
    public void setDescription(String description) { this.description = description; }
}
