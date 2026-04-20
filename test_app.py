import io
import pandas as pd
import pytest

from app import (
    normalize_key,
    to_placeholder_key,
    parse_text_recipients,
    normalize_recipients,
    render_template,
    build_preview_html,
    read_content_file,
    read_uploaded_recipients,
)


class FakeUpload:
    def __init__(self, name, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


def test_normalize_key():
    assert normalize_key("First Name!") == "firstname"
    assert normalize_key("") == ""
    assert normalize_key(None) == ""


def test_to_placeholder_key():
    assert to_placeholder_key("First Name") == "firstName"
    assert to_placeholder_key("company_name") == "companyName"
    assert to_placeholder_key("email") == "email"
    assert to_placeholder_key("") == ""


def test_parse_text_recipients_email_first():
    df = parse_text_recipients("jane@example.com, Jane Doe\nmark@example.com, Mark")
    assert len(df) == 2
    assert df.iloc[0]["email"] == "jane@example.com"
    assert df.iloc[0]["name"] == "Jane Doe"


def test_parse_text_recipients_name_first():
    df = parse_text_recipients("Jane Doe jane@example.com")
    assert df.iloc[0]["email"] == "jane@example.com"
    assert "Jane" in df.iloc[0]["name"]


def test_parse_text_recipients_skips_blank():
    df = parse_text_recipients("\n\njane@example.com\n")
    assert len(df) == 1


def test_normalize_recipients_basic():
    raw = pd.DataFrame({"Email": ["a@x.com", "B@X.com", "bad"], "Name": ["A", "B", "C"]})
    out = normalize_recipients(raw)
    assert list(out["email"]) == ["a@x.com", "b@x.com"]
    assert list(out["name"]) == ["A", "B"]


def test_normalize_recipients_dedup():
    raw = pd.DataFrame({"email": ["a@x.com", "a@x.com"], "name": ["A1", "A2"]})
    out = normalize_recipients(raw)
    assert len(out) == 1


def test_normalize_recipients_first_last():
    raw = pd.DataFrame({
        "email": ["a@x.com"],
        "First Name": ["Jane"],
        "Last Name": ["Doe"],
    })
    out = normalize_recipients(raw)
    assert out.iloc[0]["name"] == "Jane Doe"


def test_normalize_recipients_empty():
    assert normalize_recipients(pd.DataFrame()).empty


def test_render_template_double_braces():
    out = render_template("Hello {{name}} at {{email}}", {"name": "Jane", "email": "j@x.com"})
    assert out == "Hello Jane at j@x.com"


def test_render_template_missing_key_safe():
    out = render_template("Hi {{missing}}", {"name": "X"})
    assert "{{missing}}" in out or "${missing}" in out or "missing" not in out.replace("missing", "", 0)


def test_render_template_extra_columns():
    out = render_template("{{company}}", {"email": "a@x.com", "company": "Acme"})
    assert out == "Acme"


def test_build_preview_html_escapes():
    html = build_preview_html("a<b>&c\nd")
    assert "&lt;b&gt;" in html
    assert "&amp;" in html
    assert "<br>" in html


def test_read_content_file_html():
    up = FakeUpload("msg.html", b"<p>hi</p>")
    kind, body = read_content_file(up)
    assert kind == "html" and body == "<p>hi</p>"


def test_read_content_file_txt():
    up = FakeUpload("msg.txt", b"hello")
    kind, body = read_content_file(up)
    assert kind == "text" and body == "hello"


def test_read_content_file_unsupported():
    with pytest.raises(ValueError):
        read_content_file(FakeUpload("msg.pdf", b"x"))


def test_read_uploaded_recipients_csv():
    data = b"email,name\na@x.com,A\nb@x.com,B\n"
    df = read_uploaded_recipients(FakeUpload("list.csv", data))
    assert len(df) == 2


def test_read_uploaded_recipients_txt():
    data = b"a@x.com, A\nb@x.com, B\n"
    df = read_uploaded_recipients(FakeUpload("list.txt", data))
    assert len(df) == 2


def test_read_uploaded_recipients_none():
    assert read_uploaded_recipients(None).empty


def test_parse_text_recipients_name_before_email_comma():
    df = parse_text_recipients("Jane Doe, jane@example.com")
    assert df.iloc[0]["email"] == "jane@example.com"
    assert df.iloc[0]["name"] == "Jane Doe"


def test_parse_text_recipients_email_only():
    df = parse_text_recipients("solo@example.com")
    assert df.iloc[0]["email"] == "solo@example.com"
    assert df.iloc[0]["name"] == ""


def test_parse_text_recipients_three_cols():
    df = parse_text_recipients("Jane, jane@example.com, Acme")
    assert df.iloc[0]["email"] == "jane@example.com"
    assert "Jane" in df.iloc[0]["name"] and "Acme" in df.iloc[0]["name"]


def test_normalize_recipients_firstname_only():
    raw = pd.DataFrame({"email": ["a@x.com"], "First Name": ["Jane"]})
    out = normalize_recipients(raw)
    assert out.iloc[0]["name"] == "Jane"


def test_normalize_recipients_name_preferred_over_firstname():
    raw = pd.DataFrame({
        "email": ["a@x.com"],
        "Name": ["Full Name"],
        "First Name": ["Jane"],
    })
    out = normalize_recipients(raw)
    assert out.iloc[0]["name"] == "Full Name"


def test_normalize_recipients_drops_invalid_emails():
    raw = pd.DataFrame({"email": ["a@x.com", "", "no-at-sign", "b@y.co"], "name": ["A", "B", "C", "D"]})
    out = normalize_recipients(raw)
    assert list(out["email"]) == ["a@x.com", "b@y.co"]


def test_render_template_single_braces_literal():
    out = render_template("Cost: {99}", {"name": "x"})
    assert out == "Cost: {99}"
