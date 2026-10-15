-- Thay cho dbo.sp_refresh_category_monthly_revenue (SQL động EXEC(@sql) + PIVOT)
-- Danh sách tháng lấy từ MỌI đơn hàng (kể cả NEW/CANCELLED), giống @cols trong procedure,
-- nên tháng chỉ có đơn hủy vẫn có cột, giá trị NULL.
-- SQL sinh bằng vòng lặp Jinja: bỏ qua luật thụt lề LT02 cho file này
-- noqa: disable=LT02
{%- set months_query -%}
    select distinct to_char(order_date, 'YYYY-MM') as ym
    from {{ ref('stg_orders') }}
    order by 1
{%- endset -%}

{#- Trên database mới (CI, máy mới), dbt compile / docs generate chạy trước khi stg_orders
    được tạo: khi đó bỏ qua run_query thay vì lỗi. Lúc dbt build, stg_orders luôn có trước. -#}
{%- set months = [] -%}
{%- if execute and load_relation(ref('stg_orders')) is not none -%}
    {%- set months = run_query(months_query).columns[0].values() -%}
{%- endif %}

select
    category
    {%- for m in months %},
    sum(revenue) filter (where year_month = '{{ m }}') as "{{ m }}"
    {%- endfor %}
from {{ ref('int_category_monthly_revenue') }}
group by category
