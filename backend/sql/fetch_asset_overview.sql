SELECT
    asset_id,
    -- Realized Volatility (Return StdDev)
    MAX(
        CASE
            WHEN metric_type = 'return'
            AND timeframe = '1d' THEN std_dev
        END
    ) as rv_1d,
    MAX(
        CASE
            WHEN metric_type = 'return'
            AND timeframe = '1w' THEN std_dev
        END
    ) as rv_1w,
    MAX(
        CASE
            WHEN metric_type = 'return'
            AND timeframe = '1m' THEN std_dev
        END
    ) as rv_1m,
    MAX(
        CASE
            WHEN metric_type = 'return'
            AND timeframe = '1q' THEN std_dev
        END
    ) as rv_1q,
    MAX(
        CASE
            WHEN metric_type = 'return'
            AND timeframe = '1y' THEN std_dev
        END
    ) as rv_1y,
    -- Simple ATRP StdDev
    MAX(
        CASE
            WHEN metric_type = 'atrp_simple'
            AND timeframe = '1d' THEN std_dev
        END
    ) as satrp_1d,
    MAX(
        CASE
            WHEN metric_type = 'atrp_simple'
            AND timeframe = '1w' THEN std_dev
        END
    ) as satrp_1w,
    MAX(
        CASE
            WHEN metric_type = 'atrp_simple'
            AND timeframe = '1m' THEN std_dev
        END
    ) as satrp_1m,
    MAX(
        CASE
            WHEN metric_type = 'atrp_simple'
            AND timeframe = '1q' THEN std_dev
        END
    ) as satrp_1q,
    MAX(
        CASE
            WHEN metric_type = 'atrp_simple'
            AND timeframe = '1y' THEN std_dev
        END
    ) as satrp_1y,
    -- Real ATRP StdDev
    MAX(
        CASE
            WHEN metric_type = 'atrp_real'
            AND timeframe = '1d' THEN std_dev
        END
    ) as ratrp_1d,
    MAX(
        CASE
            WHEN metric_type = 'atrp_real'
            AND timeframe = '1w' THEN std_dev
        END
    ) as ratrp_1w,
    MAX(
        CASE
            WHEN metric_type = 'atrp_real'
            AND timeframe = '1m' THEN std_dev
        END
    ) as ratrp_1m,
    MAX(
        CASE
            WHEN metric_type = 'atrp_real'
            AND timeframe = '1q' THEN std_dev
        END
    ) as ratrp_1q,
    MAX(
        CASE
            WHEN metric_type = 'atrp_real'
            AND timeframe = '1y' THEN std_dev
        END
    ) as ratrp_1y
FROM
    asset_stats
GROUP BY
    asset_id;