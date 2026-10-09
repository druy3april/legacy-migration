{#- Test tùy biến: trả về các dòng có giá trị âm. 0 dòng = PASS -#}
{% test non_negative(model, column_name) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0
{% endtest %}