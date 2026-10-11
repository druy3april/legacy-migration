select category
from {{ ref('mart_top_products_by_category') }}
group by category
having
    min(rank_in_category) <> 1
    or max(rank_in_category) > 3
    or count(*) > 3
