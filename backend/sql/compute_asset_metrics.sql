-- Compute Multi-Timeframe Metrics (Returns, Simple ATRP, Real ATRP)
-- Creates table 'asset_metrics'
-- Timeframes: 1d (1), 1w (5), 1m (20), 1q (60), 1y (252)
CREATE
OR REPLACE TABLE asset_metrics AS
WITH
    adjusted_prices AS (
        SELECT
            asset_id,
            CAST(date AS DATE) as date,
            adj_close,
            -- Calculate Split-Adjusted High/Low
            CASE
                WHEN close = 0 THEN high
                ELSE high * (adj_close / close)
            END as adj_high,
            CASE
                WHEN close = 0 THEN low
                ELSE low * (adj_close / close)
            END as adj_low,
            LAG (adj_close, 1) OVER (
                PARTITION BY
                    asset_id
                ORDER BY
                    date
            ) as prev_close
        FROM
            raw_db.historical_prices_adj
    ),
    tr_calcs AS (
        SELECT
            *,
            -- True Range Calculation
            -- TR = Max(H-L, |H-Cp|, |L-Cp|)
            GREATEST (
                (adj_high - adj_low),
                ABS(adj_high - COALESCE(prev_close, adj_high)),
                ABS(adj_low - COALESCE(prev_close, adj_low))
            ) as tr
        FROM
            adjusted_prices
    )
SELECT
    asset_id,
    date,
    adj_close as close,
    -- RETURNS ----------------------------------------------------------------
    (adj_close - LAG (adj_close, 1) OVER w) / LAG (adj_close, 1) OVER w as return_1d,
    (adj_close - LAG (adj_close, 5) OVER w) / LAG (adj_close, 5) OVER w as return_1w,
    (adj_close - LAG (adj_close, 20) OVER w) / LAG (adj_close, 20) OVER w as return_1m,
    (adj_close - LAG (adj_close, 60) OVER w) / LAG (adj_close, 60) OVER w as return_1q,
    (adj_close - LAG (adj_close, 252) OVER w) / LAG (adj_close, 252) OVER w as return_1y,
    -- SIMPLE ATRP ((High - Low) / Low) ---------------------------------------
    -- Using Rolling MaxHigh - MinLow for longer timeframes (as per previous logic)
    CASE
        WHEN adj_low = 0 THEN NULL
        ELSE (adj_high - adj_low) / adj_low
    END as atrp_simple_1d,
    CASE
        WHEN MIN(adj_low) OVER w5 = 0 THEN NULL
        ELSE (MAX(adj_high) OVER w5 - MIN(adj_low) OVER w5) / MIN(adj_low) OVER w5
    END as atrp_simple_1w,
    CASE
        WHEN MIN(adj_low) OVER w20 = 0 THEN NULL
        ELSE (MAX(adj_high) OVER w20 - MIN(adj_low) OVER w20) / MIN(adj_low) OVER w20
    END as atrp_simple_1m,
    CASE
        WHEN MIN(adj_low) OVER w60 = 0 THEN NULL
        ELSE (MAX(adj_high) OVER w60 - MIN(adj_low) OVER w60) / MIN(adj_low) OVER w60
    END as atrp_simple_1q,
    CASE
        WHEN MIN(adj_low) OVER w252 = 0 THEN NULL
        ELSE (MAX(adj_high) OVER w252 - MIN(adj_low) OVER w252) / MIN(adj_low) OVER w252
    END as atrp_simple_1y,
    -- REAL ATRP (SMA(TR) / Close) --------------------------------------------
    -- 1d (Just TR/Close)
    (tr / adj_close) as atrp_real_1d,
    -- 1w (Avg TR 5d / Close)
    (AVG(tr) OVER w5) / adj_close as atrp_real_1w,
    -- 1m (Avg TR 20d / Close)
    (AVG(tr) OVER w20) / adj_close as atrp_real_1m,
    -- 1q (Avg TR 60d / Close)
    (AVG(tr) OVER w60) / adj_close as atrp_real_1q,
    -- 1y (Avg TR 252d / Close)
    (AVG(tr) OVER w252) / adj_close as atrp_real_1y
FROM
    tr_calcs
WINDOW
    w AS (
        PARTITION BY
            asset_id
        ORDER BY
            date
    ),
    -- Rolling Windows (rows between N-1 preceding and current)
    w5 AS (
        PARTITION BY
            asset_id
        ORDER BY
            date ROWS BETWEEN 4 PRECEDING
            AND CURRENT ROW
    ),
    w20 AS (
        PARTITION BY
            asset_id
        ORDER BY
            date ROWS BETWEEN 19 PRECEDING
            AND CURRENT ROW
    ),
    w60 AS (
        PARTITION BY
            asset_id
        ORDER BY
            date ROWS BETWEEN 59 PRECEDING
            AND CURRENT ROW
    ),
    w252 AS (
        PARTITION BY
            asset_id
        ORDER BY
            date ROWS BETWEEN 251 PRECEDING
            AND CURRENT ROW
    )
ORDER BY
    asset_id,
    date;