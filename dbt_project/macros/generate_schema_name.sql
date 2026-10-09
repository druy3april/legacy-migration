{#- Dùng đúng tên schema khai báo (+schema: marts -> marts), không ghép tiền tố "dbt_" -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
