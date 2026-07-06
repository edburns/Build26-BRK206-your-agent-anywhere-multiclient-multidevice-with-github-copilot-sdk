package com.microsoft.build.spike;

import java.util.List;

import jakarta.data.repository.By;
import jakarta.data.repository.Find;
import jakarta.data.repository.Insert;
import jakarta.data.repository.Query;
import jakarta.data.repository.Repository;

@Repository
public interface PropertyRepository {

    @Insert
    void save(Property property);

    @Find
    List<Property> findByCity(@By("city") String city);

    @Query("WHERE bedrooms >= ?1")
    List<Property> findLargeHomes(int minBedrooms);
}
