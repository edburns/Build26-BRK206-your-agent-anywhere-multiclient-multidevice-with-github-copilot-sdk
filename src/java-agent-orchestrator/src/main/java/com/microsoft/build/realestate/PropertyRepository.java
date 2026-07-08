package com.microsoft.build.realestate;

import java.util.List;

import jakarta.data.repository.Insert;
import jakarta.data.repository.Query;
import jakarta.data.repository.Repository;

@Repository
public interface PropertyRepository {

    @Insert
    void save(Property property);

    @Query("""
            SELECT p FROM Property p
            WHERE (?1 IS NULL OR p.type = ?1)
              AND (?2 IS NULL OR p.address.city = ?2)
              AND p.price >= ?3
              AND p.price <= ?4
              AND p.bedrooms >= ?5
              AND p.bathrooms >= ?6
            ORDER BY p.id
            """)
    List<Property> search(
            String type,
            String city,
            int minPrice,
            int maxPrice,
            int minBedrooms,
            int minBathrooms);
}
