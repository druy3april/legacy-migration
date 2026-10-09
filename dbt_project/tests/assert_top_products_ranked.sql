SELECT category
FROM {{ ref('mart_top_products_by_category') }}
GROUP BY category
HAVING MIN(rank_in_category) <> 1
    OR MAX(rank_in_category) > 3
    OR COUNT(*) > 3
