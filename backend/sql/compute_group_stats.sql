-- Compute Group Stats UNPIVOTED by Timeframe
-- Creates table 'group_stats' (group_id, timeframe, mean...)

CREATE OR REPLACE TABLE group_stats AS
WITH unpivoted AS (
    SELECT group_id, '1d' as timeframe, avg_return_1d as val FROM group_metrics
    UNION ALL
    SELECT group_id, '1w' as timeframe, avg_return_1w as val FROM group_metrics
    UNION ALL
    SELECT group_id, '1m' as timeframe, avg_return_1m as val FROM group_metrics
    UNION ALL
    SELECT group_id, '1q' as timeframe, avg_return_1q as val FROM group_metrics
    UNION ALL
    SELECT group_id, '1y' as timeframe, avg_return_1y as val FROM group_metrics
),
basic_stats AS (
    SELECT
        group_id,
        timeframe,
        COUNT(val) as count,
        AVG(val) as mean,
        STDDEV(val) as std_dev,
        MIN(val) as min_ret,
        MAX(val) as max_ret,
        SKEWNESS(val) as skewness,
        KURTOSIS(val) as kurtosis,
        MEDIAN(val) as median
    FROM unpivoted
    WHERE val IS NOT NULL
    GROUP BY group_id, timeframe
),
sigma_counts AS (
    SELECT
        u.group_id,
        u.timeframe,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 1 * bs.std_dev THEN 1 END) as count_1sigma,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 2 * bs.std_dev THEN 1 END) as count_2sigma,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 3 * bs.std_dev THEN 1 END) as count_3sigma
    FROM unpivoted u
    JOIN basic_stats bs ON u.group_id = bs.group_id AND u.timeframe = bs.timeframe
    WHERE u.val IS NOT NULL
    GROUP BY u.group_id, u.timeframe
)
SELECT
    bs.*,
    sc.count_1sigma,
    sc.count_2sigma,
    sc.count_3sigma,
    (sc.count_1sigma::DOUBLE / bs.count) as pct_1sigma,
    (sc.count_2sigma::DOUBLE / bs.count) as pct_2sigma,
    (sc.count_3sigma::DOUBLE / bs.count) as pct_3sigma
FROM basic_stats bs
JOIN sigma_counts sc ON bs.group_id = sc.group_id AND bs.timeframe = sc.timeframe;
