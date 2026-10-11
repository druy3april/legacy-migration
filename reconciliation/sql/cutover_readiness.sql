-- Điều kiện cutover: số ngày "xanh" liên tiếp tính ngược từ ngày chạy gần nhất.
-- Ngày xanh = đủ 7 báo cáo, tất cả PASS, diff_rows = 0. Ngày không chạy = ngày đỏ.
with daily as (
    select
        run_date,
        count(*) = 7 and bool_and(status = 'PASS' and diff_rows = 0) as green
    from recon.v_daily_status
    group by run_date
),

calendar as (
    select gs::date as run_date
    from (
        select
            min(run_date) as first_day,
            max(run_date) as last_day
        from daily
    ) as b
    cross join generate_series(first_day, last_day, interval '1 day') as gs
),

timeline as (
    select
        c.run_date,
        coalesce(d.green, false) as green
    from calendar as c
    left join daily as d on c.run_date = d.run_date
),

streak as (
    select
        run_date,
        green,
        sum(case when green then 0 else 1 end) over (order by run_date desc) as breaks
    from timeline
)

select
    count(*) filter (where breaks = 0) as consecutive_green_days,
    max(run_date) as last_run_date,
    count(*) filter (where breaks = 0) >= 5 as ready_for_cutover
from streak;