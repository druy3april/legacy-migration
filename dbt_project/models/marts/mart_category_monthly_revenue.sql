-- Thay cho dbo.sp_refresh_category_monthly_revenue (SQL động EXEC(@sql) + PIVOT)
-- Danh sách tháng lấy từ MỌI đơn hàng (kể cả NEW/CANCELLED), giống @cols trong procedure,
-- nên tháng chỉ có đơn hủy vẫn có cột, giá trị NULL.
{%- set months_query -%}
    select distinct to_char(order_date, 'YYYY-MM') as ym
    from {{ ref('stg_orders') }}
    order by 1
{%- endset -%}

{%- if execute -%}
    {%- set months = run_query(months_query).columns[0].values() -%}
{%- else -%}
    {%- set months = [] -%}
{%- endif %}

select
    category
    {%- for m in months %},
    sum(revenue) filter (where year_month = '{{ m }}') as "{{ m }}"
    {%- endfor %}
from {{ ref('int_category_monthly_revenue') }}
group by category