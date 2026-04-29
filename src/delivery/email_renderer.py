"""
alpha_extractor_email.py
------------------------
Populates the Alpha Extractor HTML email template with dynamic data
and returns the rendered HTML string ready to be used as `html_body`.

Usage
-----
    from alpha_extractor_email import AlphaExtractorEmail

    renderer = AlphaExtractorEmail()
    html_body = renderer.render(data)
"""

from __future__ import annotations

import html as html_lib
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Sentiment colour palette  (border / bg / text)
# ---------------------------------------------------------------------------
_SENTIMENT_STYLES: dict[str, dict] = {
    "bullish": {
        "border": "rgba(0, 255, 65, 0.3)",
        "bg": "rgba(0, 255, 65, 0.1)",
        "color": "rgb(0, 255, 65)",
        "badge": "🟢 BULLISH",
    },
    "bearish": {
        "border": "rgba(255, 0, 60, 0.3)",
        "bg": "rgba(255, 0, 60, 0.1)",
        "color": "rgb(255, 0, 60)",
        "badge": "🔴 BEARISH",
    },
    "neutral": {
        "border": "rgba(136, 136, 136, 0.3)",
        "bg": "rgba(136, 136, 136, 0.1)",
        "color": "rgb(136, 136, 136)",
        "badge": "⚪ NEUTRAL",
    },
}


def _sentiment_style(sentiment: str) -> dict:
    """Return colour dict for a sentiment string (case-insensitive, defaults to neutral)."""
    return _SENTIMENT_STYLES.get(sentiment.lower(), _SENTIMENT_STYLES["neutral"])


def _e(text: str) -> str:
    """HTML-escape a plain-text value."""
    return html_lib.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# Internal data classes (optional – callers may pass plain dicts instead)
# ---------------------------------------------------------------------------
@dataclass
class AssetData:
    ticker: str
    name: str
    sentiment: str
    catalyst: str
    actionableEdge: str


@dataclass
class DigestData:
    date: str
    macroSentiment: str
    macroSummary: str
    assets: list[AssetData]
    traceId: str = "alpha-extractor-email"

    @classmethod
    def from_dict(cls, d: dict) -> DigestData:
        assets = [AssetData(**a) if isinstance(a, dict) else a for a in d.get("assets", [])]
        return cls(
            date=d["date"],
            macroSentiment=d["macroSentiment"],
            macroSummary=d["macroSummary"],
            assets=assets,
            traceId=d.get("traceId", "alpha-extractor-email"),
        )


# ---------------------------------------------------------------------------
# SVG logo (unchanged from the Figma template)
# ---------------------------------------------------------------------------
_LOGO_SVG = """\
<svg width="36" height="36" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="60" cy="60" r="52" stroke="url(#emailRingGradient)" stroke-width="1" opacity="0.2"/>
  <g>
    <circle cx="20" cy="75" r="7" fill="url(#emailNodeGradient)" opacity="0.9"/>
    <circle cx="20" cy="75" r="4" fill="#60a5fa"/>
    <circle cx="20" cy="75" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.3"/>
    <circle cx="35" cy="95" r="7" fill="url(#emailNodeGradient)" opacity="0.9"/>
    <circle cx="35" cy="95" r="4" fill="#60a5fa"/>
    <circle cx="35" cy="95" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.3"/>
    <circle cx="60" cy="100" r="7" fill="url(#emailNodeGradient)" opacity="0.9"/>
    <circle cx="60" cy="100" r="4" fill="#60a5fa"/>
    <circle cx="60" cy="100" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.3"/>
    <circle cx="85" cy="95" r="7" fill="url(#emailNodeGradient)" opacity="0.9"/>
    <circle cx="85" cy="95" r="4" fill="#60a5fa"/>
    <circle cx="85" cy="95" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.3"/>
    <circle cx="100" cy="75" r="7" fill="url(#emailNodeGradient)" opacity="0.9"/>
    <circle cx="100" cy="75" r="4" fill="#60a5fa"/>
    <circle cx="100" cy="75" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.3"/>
  </g>
  <g>
    <line x1="20" y1="75" x2="60" y2="30" stroke="url(#emailFlowGradient)" stroke-width="2" opacity="0.5"/>
    <line x1="35" y1="95" x2="60" y2="30" stroke="url(#emailFlowGradient)" stroke-width="2" opacity="0.5"/>
    <line x1="60" y1="100" x2="60" y2="30" stroke="url(#emailFlowGradient)" stroke-width="2" opacity="0.5"/>
    <line x1="85" y1="95" x2="60" y2="30" stroke="url(#emailFlowGradient)" stroke-width="2" opacity="0.5"/>
    <line x1="100" y1="75" x2="60" y2="30" stroke="url(#emailFlowGradient)" stroke-width="2" opacity="0.5"/>
    <circle cx="40" cy="52" r="2.5" fill="#2dd4bf" opacity="0.6"/>
    <circle cx="47" cy="62" r="2.5" fill="#2dd4bf" opacity="0.6"/>
    <circle cx="60" cy="65" r="2.5" fill="#2dd4bf" opacity="0.6"/>
    <circle cx="73" cy="62" r="2.5" fill="#2dd4bf" opacity="0.6"/>
    <circle cx="80" cy="52" r="2.5" fill="#2dd4bf" opacity="0.6"/>
  </g>
  <path d="M 60 18 L 75 26 L 75 42 L 60 50 L 45 42 L 45 26 Z"
        stroke="url(#emailFrameGradient)" stroke-width="1.5" fill="none" opacity="0.4"/>
  <g>
    <circle cx="60" cy="30" r="14" fill="url(#emailGlowGradient)" opacity="0.3"/>
    <circle cx="60" cy="30" r="4.5" fill="#00E5FF" opacity="0.95"/>
    <circle cx="60" cy="30" r="2.5" fill="#ffffff" opacity="0.9"/>
    <circle cx="52" cy="22" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <circle cx="68" cy="22" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <circle cx="48" cy="30" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <circle cx="72" cy="30" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <circle cx="52" cy="38" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <circle cx="68" cy="38" r="3" fill="url(#emailInsightGradient)" opacity="0.9"/>
    <g stroke="#00E5FF" stroke-width="1" opacity="0.4">
      <line x1="60" y1="30" x2="52" y2="22"/>
      <line x1="60" y1="30" x2="68" y2="22"/>
      <line x1="60" y1="30" x2="48" y2="30"/>
      <line x1="60" y1="30" x2="72" y2="30"/>
      <line x1="60" y1="30" x2="52" y2="38"/>
      <line x1="60" y1="30" x2="68" y2="38"/>
      <line x1="52" y1="22" x2="48" y2="30" opacity="0.3"/>
      <line x1="68" y1="22" x2="72" y2="30" opacity="0.3"/>
      <line x1="48" y1="30" x2="52" y2="38" opacity="0.3"/>
      <line x1="72" y1="30" x2="68" y2="38" opacity="0.3"/>
    </g>
    <circle cx="60" cy="30" r="16" stroke="#00E5FF" stroke-width="1"
            opacity="0.3" stroke-dasharray="2,2"/>
  </g>
  <g stroke="#2dd4bf" stroke-width="1.5" opacity="0.3">
    <path d="M 10 10 L 10 18 M 10 10 L 18 10" stroke-linecap="round"/>
    <path d="M 110 10 L 110 18 M 110 10 L 102 10" stroke-linecap="round"/>
  </g>
  <defs>
    <linearGradient id="emailRingGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa"/>
      <stop offset="50%" stop-color="#2dd4bf"/>
      <stop offset="100%" stop-color="#60a5fa"/>
    </linearGradient>
    <radialGradient id="emailNodeGradient">
      <stop offset="0%" stop-color="#60a5fa"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </radialGradient>
    <linearGradient id="emailFlowGradient" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" stop-opacity="0.4"/>
      <stop offset="50%" stop-color="#2dd4bf" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#00E5FF" stop-opacity="0.9"/>
    </linearGradient>
    <linearGradient id="emailFrameGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00E5FF"/>
      <stop offset="100%" stop-color="#2dd4bf"/>
    </linearGradient>
    <radialGradient id="emailGlowGradient">
      <stop offset="0%" stop-color="#00E5FF"/>
      <stop offset="100%" stop-color="transparent"/>
    </radialGradient>
    <radialGradient id="emailInsightGradient">
      <stop offset="0%" stop-color="#00E5FF"/>
      <stop offset="100%" stop-color="#2dd4bf"/>
    </radialGradient>
  </defs>
</svg>"""


# ---------------------------------------------------------------------------
# Main renderer class
# ---------------------------------------------------------------------------
class AlphaExtractorEmail:
    """
    Renders the Alpha Extractor Daily Digest HTML email.

    Example
    -------
        renderer = AlphaExtractorEmail()
        html_body = renderer.render(data_dict)
    """

    def render(self, data: dict) -> str:
        """
        Populate the email template.

        Parameters
        ----------
        data : dict
            Must follow the schema:
            {
              "date": str,
              "macroSentiment": "bullish" | "bearish" | "neutral",
              "macroSummary": str,
              "assets": [
                {
                  "ticker": str,
                  "name": str,
                  "sentiment": "bullish" | "bearish" | "neutral",
                  "catalyst": str,
                  "actionableEdge": str
                }
              ],
              "traceId": str          # optional
            }

        Returns
        -------
        str
            Complete HTML string suitable for use as ``html_body``.
        """
        digest = DigestData.from_dict(data)
        return self._build_html(digest)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_asset_card(self, asset: AssetData) -> str:
        s = _sentiment_style(asset.sentiment)
        return f"""\
<div style="border: 1px solid {s["border"]}; border-radius: 8px; padding: 20px;
            background-color: rgba(18,18,18,0.6);">
  <!-- Ticker row -->
  <div style="display: flex; justify-content: space-between; align-items: flex-start;
              margin-bottom: 16px;">
    <div>
      <div style="font-family: 'Courier New', monospace; font-size: 16px; font-weight: 700;
                  color: rgb(255,255,255); margin-bottom: 4px;">{_e(asset.ticker)}</div>
      <div style="font-size: 13px; color: rgb(170,170,170);">{_e(asset.name)}</div>
    </div>
    <div style="background-color: {s["bg"]}; border: 1px solid {s["border"]};
                border-radius: 20px; padding: 6px 12px; font-size: 11px;
                font-family: 'Courier New', monospace; font-weight: 600;
                color: {s["color"]}; white-space: nowrap;">{s["badge"]}</div>
  </div>
  <!-- Catalyst -->
  <div style="margin-bottom: 14px;">
    <div style="font-size: 12px; font-weight: 700; color: rgb(0,229,255); margin-bottom: 6px;
                font-family: 'Courier New', monospace;">CATALYST:</div>
    <div style="font-size: 14px; line-height: 1.6; color: rgb(204,204,204);">
      {_e(asset.catalyst)}
    </div>
  </div>
  <!-- Actionable Edge -->
  <div style="background-color: rgba(0,229,255,0.05); border: 1px solid rgba(0,229,255,0.2);
              border-radius: 6px; padding: 14px;">
    <div style="font-size: 12px; font-weight: 700; color: rgb(0,229,255); margin-bottom: 6px;
                font-family: 'Courier New', monospace;">ACTIONABLE EDGE:</div>
    <div style="font-size: 14px; line-height: 1.6; color: rgb(229,229,229);">
      {_e(asset.actionableEdge)}
    </div>
  </div>
</div>"""

    def _build_html(self, d: DigestData) -> str:
        macro_s = _sentiment_style(d.macroSentiment)
        asset_cards_html = "\n".join(self._build_asset_card(a) for a in d.assets)

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Alpha Extractor - Daily Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #000000;">

  <!-- Outer wrapper -->
  <div style="max-width: 650px; margin: 0 auto; background-color: rgb(10,10,12);
              color: rgb(229,229,229);
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
              padding: 0;">

    <!-- ── HEADER ── -->
    <div style="padding: 32px 24px 24px;
                border-bottom: 1px solid rgba(100,116,139,0.3);
                background-color: rgba(15,23,42,0.5);">
      <div style="display: flex; align-items: center; justify-content: space-between;
                  margin-bottom: 12px;">

        <!-- Logo + title -->
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 40px; height: 40px; background: rgba(30,41,59,0.6);
                      border-radius: 8px; display: flex; align-items: center;
                      justify-content: center; border: 1px solid rgba(96,165,250,0.3);">
            {_LOGO_SVG}
          </div>
          <div>
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        font-size: 20px; font-weight: 600; letter-spacing: 0.5px;
                        color: rgb(226,232,240);">Alpha Extractor</div>
            <div style="font-size: 12px; color: rgb(148,163,184); margin-top: 2px;
                        font-weight: 400;">Daily Market Intelligence</div>
          </div>
        </div>

        <!-- Date -->
        <div style="font-family: 'Courier New', monospace; font-size: 11px;
                    color: rgb(136,136,136); text-align: right;">
          {_e(d.date)}
        </div>
      </div>
    </div>
    <!-- /HEADER -->

    <!-- ── BODY ── -->
    <div style="padding: 24px;">

      <!-- Macro sentiment block -->
      <div style="border: 1px solid {macro_s["border"]}; border-radius: 8px; padding: 20px;
                  background-color: rgba(18,18,18,0.6); margin-bottom: 24px;">
        <div style="display: inline-block; background-color: {macro_s["bg"]};
                    border: 1px solid {macro_s["border"]}; border-radius: 6px;
                    padding: 6px 14px; font-size: 11px; font-family: 'Courier New', monospace;
                    font-weight: 700; color: {macro_s["color"]}; letter-spacing: 0.5px;
                    margin-bottom: 14px;">
          MACRO SENTIMENT: {_e(d.macroSentiment.upper())}
        </div>
        <div style="font-size: 14px; line-height: 1.6; color: rgb(204,204,204);">
          {_e(d.macroSummary)}
        </div>
      </div>

      <!-- Asset cards -->
      <div style="display: flex; flex-direction: column; gap: 16px;">
        {asset_cards_html}
      </div>

    </div>
    <!-- /BODY -->

    <!-- ── FOOTER ── -->
    <div style="border-top: 1px solid rgb(26,26,28); padding: 24px;
                background-color: rgb(5,5,7);">
      <div style="font-size: 12px; color: rgb(102,102,102); margin-bottom: 12px;
                  text-align: center;">
        AI-Generated Intelligence. Not Financial Advice.
      </div>
      <div style="font-family: 'Courier New', monospace; font-size: 10px; color: rgb(68,68,68);
                  margin-bottom: 14px; text-align: center;">
        Trace: {_e(d.traceId)}
      </div>
      <div style="display: flex; justify-content: center; gap: 16px; font-size: 12px;">
        <a href="#" style="color: rgb(0,229,255); text-decoration: none;">Manage Preferences</a>
        <span style="color: rgb(51,51,51);">|</span>
        <a href="#" style="color: rgb(0,229,255); text-decoration: none;">Unsubscribe</a>
      </div>
    </div>
    <!-- /FOOTER -->

  </div>
</body>
</html>"""
