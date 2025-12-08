-- Compute Multi-Timeframe Metrics
-- Creates table 'asset_metrics' (formerly daily_metrics)
-- Timeframes: 1d (1), 1w (5), 1m (20), 1q (60), 1y (252)
CREATE
OR REPLACE TABLE asset_metrics AS
SELECT
    asset_id,
    CAST(date AS DATE) as date,
    adj_close as close,
    -- Daily
    (adj_close - LAG (adj_close, 1) OVER w) / LAG (adj_close, 1) OVER w as return_1d,
    -- Weekly (5d)
    (adj_close - LAG (adj_close, 5) OVER w) / LAG (adj_close, 5) OVER w as return_1w,
    -- Monthly (20d)
    (adj_close - LAG (adj_close, 20) OVER w) / LAG (adj_close, 20) OVER w as return_1m,
    -- Quarterly (60d)
    (adj_close - LAG (adj_close, 60) OVER w) / LAG (adj_close, 60) OVER w as return_1q,
    -- Yearly (252d)
    (adj_close - LAG (adj_close, 252) OVER w) / LAG (adj_close, 252) OVER w as return_1y
FROM
    raw_db.historical_prices_adj
WINDOW
    w AS (
        PARTITION BY
            asset_id
        ORDER BY
            date
    )
ORDER BY
    asset_id,
    date;