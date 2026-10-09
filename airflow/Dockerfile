FROM apache/airflow:3.3.1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements.txt

# dbt cài trong venv riêng để không xung đột thư viện với Airflow
COPY requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /home/airflow/dbt-venv \
 && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt
