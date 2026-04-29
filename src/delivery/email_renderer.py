"""
email_renderer.py
-----------------
Populates the Alpha Extractor HTML email template with dynamic data
and returns the rendered HTML string ready to be used as `html_body`.

Layout is built with <table> elements throughout — flex/grid are not
supported in Gmail, Apple Mail, or most email clients.

Usage
-----
    from email_renderer import AlphaExtractorEmail

    renderer = AlphaExtractorEmail()
    html_body = renderer.render(data)
"""

from __future__ import annotations

import html as html_lib
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Sentiment colour palette
# ---------------------------------------------------------------------------
_SENTIMENT_STYLES: dict[str, dict] = {
    "bullish": {
        "border": "rgba(0, 255, 65, 0.3)",
        "bg": "rgba(0, 255, 65, 0.1)",
        "color": "rgb(0, 255, 65)",
        "badge": "&#x1F7E2; BULLISH",
    },
    "bearish": {
        "border": "rgba(255, 0, 60, 0.3)",
        "bg": "rgba(255, 0, 60, 0.1)",
        "color": "rgb(255, 0, 60)",
        "badge": "&#x1F534; BEARISH",
    },
    "neutral": {
        "border": "rgba(136, 136, 136, 0.3)",
        "bg": "rgba(136, 136, 136, 0.1)",
        "color": "rgb(136, 136, 136)",
        "badge": "&#x26AA; NEUTRAL",
    },
}


def _sentiment_style(sentiment: str) -> dict:
    """Return colour dict for a sentiment string (case-insensitive, defaults to neutral)."""
    return _SENTIMENT_STYLES.get(sentiment.lower(), _SENTIMENT_STYLES["neutral"])


def _e(text: str) -> str:
    """HTML-escape a plain-text value."""
    return html_lib.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class AssetData:
    ticker: str
    name: str
    sentiment: str
    catalyst: str
    actionableEdge: str  # noqa: N815


@dataclass
class DigestData:
    date: str
    macroSentiment: str  # noqa: N815
    macroSummary: str  # noqa: N815
    assets: list[AssetData]
    traceId: str = "alpha-extractor-email"  # noqa: N815

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
# SVG logo
# ---------------------------------------------------------------------------
# Email-safe SVG: uses only flat fill/stroke hex colours — no url(#gradient)
# references, which are stripped by Gmail and most email clients.
_LOGO_SVG = (
    '<svg width="36" height="36" viewBox="0 0 120 120" fill="none"'
    ' xmlns="http://www.w3.org/2000/svg">'
    # outer ring
    '<circle cx="60" cy="60" r="52" stroke="#60a5fa" stroke-width="1" opacity="0.2"/>'
    # corner brackets
    '<g stroke="#2dd4bf" stroke-width="1.5" opacity="0.4">'
    '<path d="M10 10 L10 18 M10 10 L18 10" stroke-linecap="round"/>'
    '<path d="M110 10 L110 18 M110 10 L102 10" stroke-linecap="round"/>'
    "</g>"
    # flow lines from bottom nodes up to central hub
    '<g stroke="#2dd4bf" stroke-width="2" opacity="0.45">'
    '<line x1="20" y1="75" x2="60" y2="30"/>'
    '<line x1="35" y1="95" x2="60" y2="30"/>'
    '<line x1="60" y1="100" x2="60" y2="30"/>'
    '<line x1="85" y1="95" x2="60" y2="30"/>'
    '<line x1="100" y1="75" x2="60" y2="30"/>'
    "</g>"
    # bottom network nodes
    "<g>"
    '<circle cx="20" cy="75" r="7" fill="#3b82f6" opacity="0.9"/>'
    '<circle cx="20" cy="75" r="4" fill="#60a5fa"/>'
    '<circle cx="20" cy="75" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.25"/>'
    '<circle cx="35" cy="95" r="7" fill="#3b82f6" opacity="0.9"/>'
    '<circle cx="35" cy="95" r="4" fill="#60a5fa"/>'
    '<circle cx="35" cy="95" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.25"/>'
    '<circle cx="60" cy="100" r="7" fill="#3b82f6" opacity="0.9"/>'
    '<circle cx="60" cy="100" r="4" fill="#60a5fa"/>'
    '<circle cx="60" cy="100" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.25"/>'
    '<circle cx="85" cy="95" r="7" fill="#3b82f6" opacity="0.9"/>'
    '<circle cx="85" cy="95" r="4" fill="#60a5fa"/>'
    '<circle cx="85" cy="95" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.25"/>'
    '<circle cx="100" cy="75" r="7" fill="#3b82f6" opacity="0.9"/>'
    '<circle cx="100" cy="75" r="4" fill="#60a5fa"/>'
    '<circle cx="100" cy="75" r="10" stroke="#60a5fa" stroke-width="1" opacity="0.25"/>'
    "</g>"
    # flow signal dots along lines
    '<g fill="#2dd4bf" opacity="0.7">'
    '<circle cx="40" cy="52" r="2.5"/>'
    '<circle cx="47" cy="62" r="2.5"/>'
    '<circle cx="60" cy="65" r="2.5"/>'
    '<circle cx="73" cy="62" r="2.5"/>'
    '<circle cx="80" cy="52" r="2.5"/>'
    "</g>"
    # hexagon frame around hub
    '<path d="M60 18 L75 26 L75 42 L60 50 L45 42 L45 26 Z"'
    ' stroke="#00E5FF" stroke-width="1.5" fill="none" opacity="0.35"/>'
    # hub glow ring
    '<circle cx="60" cy="30" r="16" stroke="#00E5FF" stroke-width="1"'
    ' opacity="0.25" stroke-dasharray="2,2"/>'
    # hub satellite nodes + connector spokes
    '<g stroke="#00E5FF" stroke-width="1" opacity="0.4">'
    '<line x1="60" y1="30" x2="52" y2="22"/>'
    '<line x1="60" y1="30" x2="68" y2="22"/>'
    '<line x1="60" y1="30" x2="48" y2="30"/>'
    '<line x1="60" y1="30" x2="72" y2="30"/>'
    '<line x1="60" y1="30" x2="52" y2="38"/>'
    '<line x1="60" y1="30" x2="68" y2="38"/>'
    "</g>"
    '<g fill="#00E5FF" opacity="0.9">'
    '<circle cx="52" cy="22" r="3"/>'
    '<circle cx="68" cy="22" r="3"/>'
    '<circle cx="48" cy="30" r="3"/>'
    '<circle cx="72" cy="30" r="3"/>'
    '<circle cx="52" cy="38" r="3"/>'
    '<circle cx="68" cy="38" r="3"/>'
    "</g>"
    # central hub dot
    '<circle cx="60" cy="30" r="4.5" fill="#00E5FF" opacity="0.95"/>'
    '<circle cx="60" cy="30" r="2.5" fill="#ffffff" opacity="0.9"/>'
    "</svg>"
)


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
            Must follow the schema::

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
                  "traceId": str   # optional
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
        # Each card is a single-column table cell; the ticker/badge row
        # uses a nested two-cell table so the badge stays right-aligned
        # in every email client.
        return (
            '<tr><td style="padding: 0 0 16px 0;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border: 1px solid {s["border"]}; border-radius: 8px;'
            f' background-color: rgba(18,18,18,0.6);">'
            '<tr><td style="padding: 20px;">'
            # — ticker / badge row —
            '<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            ' style="margin-bottom: 16px;">'
            "<tr>"
            '<td style="vertical-align: top;">'
            f"<div style=\"font-family: 'Courier New', monospace; font-size: 16px;"
            f" font-weight: 700; color: rgb(255,255,255);"
            f' margin-bottom: 4px;">{_e(asset.ticker)}</div>'
            f'<div style="font-size: 13px;'
            f' color: rgb(170,170,170);">{_e(asset.name)}</div>'
            "</td>"
            '<td style="vertical-align: top; text-align: right; white-space: nowrap;">'
            f'<span style="display: inline-block; background-color: {s["bg"]};'
            f" border: 1px solid {s['border']}; border-radius: 20px;"
            f" padding: 6px 12px; font-size: 11px;"
            f" font-family: 'Courier New', monospace; font-weight: 600;"
            f' color: {s["color"]};">{s["badge"]}</span>'
            "</td>"
            "</tr>"
            "</table>"
            # — catalyst —
            '<div style="margin-bottom: 14px;">'
            '<div style="font-size: 12px; font-weight: 700; color: rgb(0,229,255);'
            " margin-bottom: 6px;"
            " font-family: 'Courier New', monospace;\">CATALYST:</div>"
            f'<div style="font-size: 14px; line-height: 1.6;'
            f' color: rgb(204,204,204);">{_e(asset.catalyst)}</div>'
            "</div>"
            # — actionable edge —
            '<div style="background-color: rgba(0,229,255,0.05);'
            " border: 1px solid rgba(0,229,255,0.2);"
            ' border-radius: 6px; padding: 14px;">'
            '<div style="font-size: 12px; font-weight: 700; color: rgb(0,229,255);'
            " margin-bottom: 6px;"
            " font-family: 'Courier New', monospace;\">ACTIONABLE EDGE:</div>"
            f'<div style="font-size: 14px; line-height: 1.6;'
            f' color: rgb(229,229,229);">{_e(asset.actionableEdge)}</div>'
            "</div>"
            "</td></tr>"
            "</table>"
            "</td></tr>"
        )

    def _build_html(self, d: DigestData) -> str:
        macro_s = _sentiment_style(d.macroSentiment)
        asset_rows_html = "".join(self._build_asset_card(a) for a in d.assets)

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            "  <title>Alpha Extractor - Daily Digest</title>\n"
            "</head>\n"
            '<body style="margin: 0; padding: 0; background-color: #000000;">\n'
            # ── outer wrapper ──
            '<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            ' style="background-color: #000000;">'
            '<tr><td align="center" style="padding: 0;">'
            '<table width="650" cellpadding="0" cellspacing="0" border="0"'
            ' style="max-width: 650px; background-color: rgb(10,10,12);'
            " color: rgb(229,229,229);"
            " font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\">"
            # ── HEADER ──
            '<tr><td style="padding: 32px 24px 24px;'
            " border-bottom: 1px solid rgba(100,116,139,0.3);"
            ' background-color: rgba(15,23,42,0.5);">'
            '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            "<tr>"
            # logo icon cell
            '<td width="40" style="vertical-align: middle; padding-right: 12px;">'
            '<div style="width: 40px; height: 40px;'
            " background: rgba(30,41,59,0.6); border-radius: 8px;"
            " border: 1px solid rgba(96,165,250,0.3);"
            " text-align: center; line-height: 40px; vertical-align: middle;"
            ' display: inline-block;">'
            f"{_LOGO_SVG}"
            "</div>"
            "</td>"
            # title + subtitle cell
            '<td style="vertical-align: middle;">'
            '<div style="font-family: -apple-system, BlinkMacSystemFont,'
            " 'Segoe UI', sans-serif; font-size: 20px; font-weight: 600;"
            ' letter-spacing: 0.5px; color: rgb(226,232,240);">Alpha Extractor</div>'
            '<div style="font-size: 12px; color: rgb(148,163,184);'
            ' margin-top: 2px; font-weight: 400;">Daily Market Intelligence</div>'
            "</td>"
            # date cell — right-aligned
            '<td style="vertical-align: middle; text-align: right;'
            " font-family: 'Courier New', monospace; font-size: 11px;"
            f' color: rgb(136,136,136); white-space: nowrap;">{_e(d.date)}</td>'
            "</tr>"
            "</table>"
            "</td></tr>"
            # ── BODY ──
            '<tr><td style="padding: 24px;">'
            # macro block
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border: 1px solid {macro_s["border"]}; border-radius: 8px;'
            f' background-color: rgba(18,18,18,0.6); margin-bottom: 24px;">'
            '<tr><td style="padding: 20px;">'
            f'<div style="display: inline-block; background-color: {macro_s["bg"]};'
            f" border: 1px solid {macro_s['border']}; border-radius: 6px;"
            f" padding: 6px 14px; font-size: 11px;"
            f" font-family: 'Courier New', monospace; font-weight: 700;"
            f" color: {macro_s['color']}; letter-spacing: 0.5px;"
            f' margin-bottom: 14px;">MACRO SENTIMENT: {_e(d.macroSentiment.upper())}</div>'
            f'<div style="font-size: 14px; line-height: 1.6;'
            f' color: rgb(204,204,204);">{_e(d.macroSummary)}</div>'
            "</td></tr>"
            "</table>"
            # asset cards
            '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            f"{asset_rows_html}"
            "</table>"
            "</td></tr>"
            # ── FOOTER ──
            '<tr><td style="border-top: 1px solid rgb(26,26,28);'
            ' padding: 24px; background-color: rgb(5,5,7); text-align: center;">'
            '<div style="font-size: 12px; color: rgb(102,102,102);'
            ' margin-bottom: 12px;">AI-Generated Intelligence. Not Financial Advice.</div>'
            "<div style=\"font-family: 'Courier New', monospace; font-size: 10px;"
            f' color: rgb(68,68,68); margin-bottom: 14px;">Trace: {_e(d.traceId)}</div>'
            '<div style="font-size: 12px;">'
            '<a href="#" style="color: rgb(0,229,255);'
            ' text-decoration: none;">Manage Preferences</a>'
            '<span style="color: rgb(51,51,51); margin: 0 8px;">|</span>'
            '<a href="#" style="color: rgb(0,229,255);'
            ' text-decoration: none;">Unsubscribe</a>'
            "</div>"
            "</td></tr>"
            "</table>"
            "</td></tr>"
            "</table>\n"
            "</body>\n"
            "</html>"
        )
