-- Per-table CDC apply state of the Spanner -> BQ mirror.
--   last_append_minute: last minute Datastream wrote to the table (Write API).
--   watermark: BQ time up to which received changes are merged into the table.
--   unapplied_span_min: minutes of received changes not yet applied, i.e.
--     (end of last append bucket) - watermark; 0 = nothing left to apply.
--   pending: BQ has received changes it has not applied yet.
--   appended_last_15min: table was written in the last 15 minutes.
WITH tbl AS (
  SELECT table_name, upsert_stream_apply_watermark AS watermark
  FROM `datcom-store.spanner_dc_graph_prod_DEFAULT.INFORMATION_SCHEMA.TABLES`
  WHERE table_type = 'BASE TABLE'
),
app AS (
  SELECT table_id AS table_name, MAX(start_timestamp) AS last_append_minute
  FROM `datcom-store.region-us.INFORMATION_SCHEMA.WRITE_API_TIMELINE_BY_PROJECT`
  WHERE dataset_id = 'spanner_dc_graph_prod_DEFAULT'
    AND start_timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  GROUP BY 1
)
SELECT
  table_name,
  last_append_minute,
  watermark,
  GREATEST(0, ROUND(TIMESTAMP_DIFF(TIMESTAMP_ADD(last_append_minute, INTERVAL 1 MINUTE),
                                   watermark, SECOND) / 60, 1)) AS unapplied_span_min,
  last_append_minute IS NOT NULL
    AND (watermark IS NULL
         OR watermark < TIMESTAMP_ADD(last_append_minute, INTERVAL 1 MINUTE)) AS pending,
  last_append_minute IS NOT NULL
    AND TIMESTAMP_ADD(last_append_minute, INTERVAL 1 MINUTE)
        > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE) AS appended_last_15min
FROM tbl LEFT JOIN app USING (table_name)
ORDER BY pending DESC, unapplied_span_min DESC, table_name;
