"""Regression tests for CSV exports in the consolidated activity report."""

import csv
import io

from app.routes.activity_reporting import _csv_response


def test_csv_response_uses_utf8_bom_semicolon_delimiter_and_download_filename():
    response = _csv_response(
        "rapport_test.csv",
        ["Collaborateur", "CA animation (FCFA)"],
        [["Équipe Sénégal", 125000]],
    )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert response.headers["Content-Disposition"] == 'attachment; filename="rapport_test.csv"'
    assert response.get_data().startswith(b"\\xef\\xbb\\xbf")

    text = response.get_data(as_text=True).lstrip("\\ufeff")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert rows == [
        ["Collaborateur", "CA animation (FCFA)"],
        ["Équipe Sénégal", "125000"],
    ]


def test_csv_response_quotes_values_containing_separator():
    response = _csv_response("rapport_test.csv", ["Nom"], [["Pharmacie A; B"]])
    text = response.get_data(as_text=True).lstrip("\\ufeff")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert rows == [["Nom"], ["Pharmacie A; B"]]
