-- Compute Group Metrics for ALL Timeframes
-- Creates a table 'group_metrics'
-- Logic: Only compute average if ALL assets in the group have data for that date.
CREATE
OR REPLACE TABLE group_metrics AS
WITH
    group_counts AS (
        SELECT
            group_id,
            COUNT(asset_id) as total_assets
        FROM
            raw_db.group_assets
        GROUP BY
            group_id
    ),
    daily_group_stats AS (
        SELECT
            ga.group_id,
            g.name as group_name,
            am.date,
            COUNT(am.asset_id) as current_count,
            -- Averages
            AVG(am.return_1d) as avg_return_1d,
            AVG(am.return_1w) as avg_return_1w,
            AVG(am.return_1m) as avg_return_1m,
            AVG(am.return_1q) as avg_return_1q,
            AVG(am.return_1y) as avg_return_1y
        FROM
            asset_metrics am
            JOIN raw_db.group_assets ga ON am.asset_id = ga.asset_id
            JOIN raw_db.groups g ON ga.group_id = g.group_id
        GROUP BY
            ga.group_id,
            g.name,
            am.date
    )
SELECT
    ds.group_id,
    ds.group_name,
    ds.date,
    ds.current_count as asset_count,
    ds.avg_return_1d,
    ds.avg_return_1w,
    ds.avg_return_1m,
    ds.avg_return_1q,
    ds.avg_return_1y
FROM
    daily_group_stats ds
    JOIN group_counts gc ON ds.group_id = gc.group_id
WHERE
    ds.current_count = gc.total_assets
ORDER BY
    ds.group_id,
    ds.date;