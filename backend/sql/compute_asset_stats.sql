-- Compute Statistics for Assets (Returns, Simple ATRP, Real ATRP)
CREATE
OR REPLACE TABLE asset_stats AS
WITH
    unpivoted AS (
        -- RETURNS
        SELECT
            asset_id,
            '1d' as timeframe,
            'return' as metric_type,
            return_1d as val
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1w',
            'return',
            return_1w
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1m',
            'return',
            return_1m
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1q',
            'return',
            return_1q
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1y',
            'return',
            return_1y
        FROM
            asset_metrics
            -- SIMPLE ATRP
        UNION ALL
        SELECT
            asset_id,
            '1d',
            'atrp_simple',
            atrp_simple_1d
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1w',
            'atrp_simple',
            atrp_simple_1w
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1m',
            'atrp_simple',
            atrp_simple_1m
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1q',
            'atrp_simple',
            atrp_simple_1q
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1y',
            'atrp_simple',
            atrp_simple_1y
        FROM
            asset_metrics
            -- REAL ATRP
        UNION ALL
        SELECT
            asset_id,
            '1d',
            'atrp_real',
            atrp_real_1d
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1w',
            'atrp_real',
            atrp_real_1w
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1m',
            'atrp_real',
            atrp_real_1m
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1q',
            'atrp_real',
            atrp_real_1q
        FROM
            asset_metrics
        UNION ALL
        SELECT
            asset_id,
            '1y',
            'atrp_real',
            atrp_real_1y
        FROM
            asset_metrics
    ),
    stats AS (
        SELECT
            asset_id,
            timeframe,
            metric_type,
            COUNT(val) as count_val,
            AVG(val) as mean,
            MEDIAN (val) as median,
            STDDEV (val) as std_dev,
            MIN(val) as min_ret,
            MAX(val) as max_ret,
            SKEWNESS (val) as skewness,
            KURTOSIS (val) as kurtosis
        FROM
            unpivoted
        WHERE
            val IS NOT NULL
        GROUP BY
            asset_id,
            timeframe,
            metric_type
    ),
    sigma_calcs AS (
        SELECT
            u.asset_id,
            u.timeframe,
            u.metric_type,
            s.mean,
            s.std_dev,
            -- Check if value is within N sigmas
            CASE
                WHEN ABS(u.val - s.mean) <= s.std_dev THEN 1.0
                ELSE 0.0
            END as in_1sigma,
            CASE
                WHEN ABS(u.val - s.mean) <= 2 * s.std_dev THEN 1.0
                ELSE 0.0
            END as in_2sigma,
            CASE
                WHEN ABS(u.val - s.mean) <= 3 * s.std_dev THEN 1.0
                ELSE 0.0
            END as in_3sigma
        FROM
            unpivoted u
            JOIN stats s ON u.asset_id = s.asset_id
            AND u.timeframe = s.timeframe
            AND u.metric_type = s.metric_type
        WHERE
            u.val IS NOT NULL
    )
SELECT
    s.asset_id,
    s.timeframe,
    s.metric_type,
    s.count_val as count,
    s.mean,
    s.median,
    s.std_dev,
    s.min_ret,
    s.max_ret,
    s.skewness,
    s.kurtosis,
    AVG(sc.in_1sigma) as pct_1sigma,
    AVG(sc.in_2sigma) as pct_2sigma,
    AVG(sc.in_3sigma) as pct_3sigma
FROM
    stats s
    JOIN sigma_calcs sc ON s.asset_id = sc.asset_id
    AND s.timeframe = sc.timeframe
    AND s.metric_type = sc.metric_type
GROUP BY
    s.asset_id,
    s.timeframe,
    s.metric_type,
    s.count_val,
    s.mean,
    s.median,
    s.std_dev,
    s.min_ret,
    s.max_ret,
    s.skewness,
    s.kurtosis;