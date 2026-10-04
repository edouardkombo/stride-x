import pandas as pd
from stride_x import StrideXEngine

def test_smoke_synthetic():
    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=30).tolist() * 2,
        "Market": ["A"] * 30 + ["B"] * 30,
        "Platform": ["P1"] * 60,
        "Profit": [1000.0] * 59 + [-2_000_000.0],
        "Stake": [50_000.0] * 60,
        "Actives": [100] * 60,
        "Game Count": [1000] * 60,
    })
    # make company day still positive on last day via market A
    df.loc[df.index[-1], "Profit"] = -2_000_000.0
    df.loc[29, "Profit"] = 3_000_000.0  # same date, market A offsets
    result = StrideXEngine().run(df)
    assert result["finding_count"] >= 1
    assert "roles" in result
