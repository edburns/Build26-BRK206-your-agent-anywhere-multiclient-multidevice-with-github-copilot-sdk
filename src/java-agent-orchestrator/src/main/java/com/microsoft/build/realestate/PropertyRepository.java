package com.microsoft.build.realestate;

import java.util.List;

import jakarta.data.repository.By;
import jakarta.data.repository.Insert;
import jakarta.data.repository.Query;
import jakarta.data.repository.Repository;

@Repository
public interface PropertyRepository {

    @Insert
    void save(Property property);

    @Query("""
            WHERE (?1 IS NULL OR type = ?1)
              AND (?2 IS NULL OR address.city = ?2)
              AND price >= ?3
              AND price <= ?4
              AND bedrooms >= ?5
              AND bathrooms >= ?6
            ORDER BY id
            """)
    List<Property> search(
            @By("type") String type,
            @By("address.city") String city,
            @By("price") int minPrice,
            @By("price") int maxPrice,
            @By("bedrooms") int minBedrooms,
            @By("bathrooms") int minBathrooms);
}
