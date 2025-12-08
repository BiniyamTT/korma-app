-- Compute Comprehensive Stats UNPIVOTED by Timeframe
-- Creates table 'asset_stats' (asset_id, timeframe, mean, std...)

CREATE OR REPLACE TABLE asset_stats AS
WITH unpivoted AS (
    SELECT asset_id, '1d' as timeframe, return_1d as val FROM asset_metrics
    UNION ALL
    SELECT asset_id, '1w' as timeframe, return_1w as val FROM asset_metrics
    UNION ALL
    SELECT asset_id, '1m' as timeframe, return_1m as val FROM asset_metrics
    UNION ALL
    SELECT asset_id, '1q' as timeframe, return_1q as val FROM asset_metrics
    UNION ALL
    SELECT asset_id, '1y' as timeframe, return_1y as val FROM asset_metrics
),
basic_stats AS (
    SELECT
        asset_id,
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
    GROUP BY asset_id, timeframe
),
sigma_counts AS (
    -- Compute Sigmas
    -- Note: We join unpivoted back to basic_stats on asset AND timeframe
    SELECT
        u.asset_id,
        u.timeframe,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 1 * bs.std_dev THEN 1 END) as count_1sigma,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 2 * bs.std_dev THEN 1 END) as count_2sigma,
        COUNT(CASE WHEN ABS(u.val - bs.mean) <= 3 * bs.std_dev THEN 1 END) as count_3sigma
    FROM unpivoted u
    JOIN basic_stats bs ON u.asset_id = bs.asset_id AND u.timeframe = bs.timeframe
    WHERE u.val IS NOT NULL
    GROUP BY u.asset_id, u.timeframe
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
JOIN sigma_counts sc ON bs.asset_id = sc.asset_id AND bs.timeframe = sc.timeframe;
