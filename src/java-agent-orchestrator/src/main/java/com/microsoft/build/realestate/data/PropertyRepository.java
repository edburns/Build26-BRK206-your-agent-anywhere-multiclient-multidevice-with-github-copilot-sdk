package com.microsoft.build.realestate.data;

import com.microsoft.build.realestate.Property;
import jakarta.data.repository.BasicRepository;
import jakarta.data.repository.By;
import jakarta.data.repository.Find;
import jakarta.data.repository.Query;
import jakarta.data.repository.Repository;
import java.util.List;

/**
 * Jakarta Data repository for Property entities.
 * Extends BasicRepository to inherit save() and findAll() (as Stream).
 * Uses @By annotations for explicit parameter binding (no -parameters compiler flag needed).
 */
@Repository
public interface PropertyRepository extends BasicRepository<Property, Long> {

    @Find
    List<Property> findByType(@By("type") String type);

    @Find
    List<Property> findByCity(@By("city") String city);

    @Query("WHERE p.bedrooms >= ?1")
    List<Property> findByBedroomsAtLeast(int minBedrooms);

    @Query("WHERE p.priceGbp <= ?1")
    List<Property> findByPriceAtMost(double maxPrice);
}
