{
  "job_name": "{{ job_name }}",
  "control_name": "{{ control_name }}",
  "source": {
    "name": "{{ source_name }}",
    "type": "{{ source_type }}",
    "table": "{{ source_table }}"
  },
  "primary_destination": {
    "name": "{{ primary_destination_name }}",
    "type": "{{ primary_destination_type }}",
    "target_table": "{{ primary_target_schema }}.{{ primary_target_table }}",
    "write_mode": "{{ primary_write_mode }}"
  },
  "datalake_destination": {
    "name": "{{ datalake_destination_name }}",
    "target_path": "{{ datalake_target_path }}",
    "file_format": "{{ file_format }}",
    "partition_columns": "{{ partition_columns }}"
  }
}
