-- Compute Statistics for Groups (Returns, Simple ATRP, Real ATRP)
CREATE
OR REPLACE TABLE group_stats AS
WITH
    unpivoted AS (
        -- RETURNS
        SELECT
            group_id,
            '1d' as timeframe,
            'return' as metric_type,
            avg_return_1d as val
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1w',
            'return',
            avg_return_1w
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1m',
            'return',
            avg_return_1m
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1q',
            'return',
            avg_return_1q
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1y',
            'return',
            avg_return_1y
        FROM
            group_metrics
            -- SIMPLE ATRP
        UNION ALL
        SELECT
            group_id,
            '1d',
            'atrp_simple',
            avg_atrp_simple_1d
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1w',
            'atrp_simple',
            avg_atrp_simple_1w
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1m',
            'atrp_simple',
            avg_atrp_simple_1m
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1q',
            'atrp_simple',
            avg_atrp_simple_1q
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1y',
            'atrp_simple',
            avg_atrp_simple_1y
        FROM
            group_metrics
            -- REAL ATRP
        UNION ALL
        SELECT
            group_id,
            '1d',
            'atrp_real',
            avg_atrp_real_1d
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1w',
            'atrp_real',
            avg_atrp_real_1w
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1m',
            'atrp_real',
            avg_atrp_real_1m
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1q',
            'atrp_real',
            avg_atrp_real_1q
        FROM
            group_metrics
        UNION ALL
        SELECT
            group_id,
            '1y',
            'atrp_real',
            avg_atrp_real_1y
        FROM
            group_metrics
    ),
    stats AS (
        SELECT
            group_id,
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
            group_id,
            timeframe,
            metric_type
    ),
    sigma_calcs AS (
        SELECT
            u.group_id,
            u.timeframe,
            u.metric_type,
            s.mean,
            s.std_dev,
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
            JOIN stats s ON u.group_id = s.group_id
            AND u.timeframe = s.timeframe
            AND u.metric_type = s.metric_type
        WHERE
            u.val IS NOT NULL
    )
SELECT
    s.group_id,
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
    JOIN sigma_calcs sc ON s.group_id = sc.group_id
    AND s.timeframe = sc.timeframe
    AND s.metric_type = sc.metric_type
GROUP BY
    s.group_id,
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