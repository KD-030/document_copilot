from app.ingestion.parser import parse_filing_html


def test_parse_filing_html_removes_hidden_content_and_keeps_tables(tmp_path) -> None:
    filing = tmp_path / "filing.html"
    filing.write_text(
        """
        <html><head><title>Ignored</title></head><body>
          <h1>Item 1. Business</h1>
          <p>Visible &amp; readable text.</p>
          <p hidden>Hidden attribute text</p>
          <span style="display:none">Hidden style text</span>
          <table><tr><td>Revenue</td><td>100</td></tr></table>
          <script>Ignored script</script>
        </body></html>
        """,
        encoding="utf-8",
    )

    text = parse_filing_html(filing)

    assert "Item 1. Business" in text
    assert "Visible & readable text." in text
    assert "Revenue" in text and "100" in text
    assert "Hidden attribute text" not in text
    assert "Hidden style text" not in text
    assert "Ignored" not in text
