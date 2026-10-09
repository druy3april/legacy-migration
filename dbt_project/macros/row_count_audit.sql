{#- Tạo bảng lưu số dòng mỗi lần chạy (gọi ở on-run-start) -#}
{% macro create_row_count_audit() %}
    create schema if not exists audit;
    create table if not exists audit.row_counts (
        run_at      timestamptz not null,
        model_name  text        not null,
        row_count   bigint      not null
    );
{% endmacro %}

{#- Ghi số dòng các model table sau khi build (gọi ở on-run-end).
    Chỉ ghi khi cả lần chạy không có lỗi, để lần chạy hỏng không trở thành "mốc" so sánh mới. -#}
{% macro log_row_counts(results) %}
    {% if execute %}
        {% set ns = namespace(has_failure=false, statements=[]) %}
        {% for res in results %}
            {% if res.status in ['error', 'fail'] %}
                {% set ns.has_failure = true %}
            {% endif %}
        {% endfor %}
        {% if not ns.has_failure %}
            {% for res in results %}
                {% if res.node.resource_type == 'model' and res.status == 'success'
                      and res.node.config.materialized == 'table' %}
                    {% do ns.statements.append(
                        "insert into audit.row_counts select now(), '" ~ res.node.name
                        ~ "', count(*) from " ~ res.node.relation_name
                    ) %}
                {% endif %}
            {% endfor %}
        {% endif %}
        {{ return(ns.statements | join(';\n')) }}
    {% endif %}
{% endmacro %}