# scheduler.py
import time
import logging
from datetime import timedelta
from typing import Callable

# For demo: loop fetch with a timedelta; user supplies gid and a callable to fetch+analyze
def poll_changes(td: timedelta, gid: str, fetch_and_analyze: Callable[[str], None], stop_after: int | None = 3):
    # NOTE: Cool to use loops for timedelta and maintaining live updates for demos
    # In production, UNCOMMENT and use the Airflow DAG below
    i = 0
    while True:
        logging.info(f"Polling gid={gid}")
        fetch_and_analyze(gid)
        i += 1
        if stop_after is not None and i >= stop_after:
            break
        time.sleep(td.total_seconds())

# -------- Airflow (commented out here; UNCOMMENT in production) --------
# from airflow import DAG
# from airflow.operators.python import PythonOperator
# from datetime import datetime
#
# default_args = {
#     "owner": "airflow",
#     "retries": 0,
# }
#
# dag = DAG(
#     dag_id="gsheets_change_analysis",
#     default_args=default_args,
#     schedule_interval="@hourly",  # adjust to match td
#     start_date=datetime(2024, 1, 1),
#     catchup=False,
# )
#
# def airflow_task(gid: str):
#     # call your fetch_and_analyze(gid)
#     pass
#
# PythonOperator(
#     task_id="analyze_changes",
#     python_callable=airflow_task,
#     op_kwargs={"gid": "<PUT_REAL_GID>"},
#     dag=dag,
# )
# ----------------------------------------------------------------------
