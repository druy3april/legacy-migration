{#- Biến list Jinja thành ('A', 'B', 'C') để dùng trong mệnh đề IN -#}
{% macro in_list(expression, values) -%}
    {{ expression }} IN (
        {%- for value in values -%}
            {{ dbt.string_literal(value) }}{% if not loop.last %}, {% endif %}
        {%- endfor -%}
    )
{%- endmacro %}