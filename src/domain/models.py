from pydantic import BaseModel


class AssetContext(BaseModel):
    """
    The unified Security Master entity.
    Decouples our internal system from third-party vendor naming conventions.
    """

    internal_symbol: str  # Our primary key (e.g., "NIFTY_50")
    company_name: str  # Natural language (e.g., "Nifty 50")
    yfinance_symbol: str | None = None  # Yahoo specific (e.g., "^NSEI")
    screener_symbol: str | None = None  # Screener specific (e.g., "NIFTY")
    nse_symbol: str | None = None  # NSE specific (e.g., "NIFTY 50")
    amfi_code: str | None = None  # Mutual fund specific
