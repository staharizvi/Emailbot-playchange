import io
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Gmail Email Bot",
    layout="wide",
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", str(value or "")).strip().lower()


def to_placeholder_key(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", " ", str(value or "")).strip()
    parts = [part for part in text.split(" ") if part]
    if not parts:
        return ""
    return parts[0].lower() + "".join(part.title() for part in parts[1:])


def parse_text_recipients(raw_text: str) -> pd.DataFrame:
    rows = []
    for line in str(raw_text or "").replace("\r", "").split("\n"):
        cleaned = line.strip()
        if not cleaned:
            continue

        email = ""
        name = ""

        if "," in cleaned:
            parts = [part.strip() for part in cleaned.split(",")]
            email_index = next((i for i, part in enumerate(parts) if "@" in part), -1)
            if email_index >= 0:
                email = parts[email_index]
                name = ", ".join(parts[:email_index] + parts[email_index + 1:]).strip()
            else:
                name = cleaned
        else:
            words = cleaned.split()
            email_candidates = [word for word in words if "@" in word]
            if email_candidates:
                email = email_candidates[0].strip(",;")
                name = " ".join(word for word in words if word != email_candidates[0]).strip(" ,-")
            else:
                name = cleaned

        rows.append({"email": email, "name": name})

    return pd.DataFrame(rows)


def read_uploaded_recipients(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    file_name = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if file_name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes))
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")

    if file_name.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")

    if file_name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")

    if file_name.endswith(".txt"):
        try:
            return parse_text_recipients(file_bytes.decode("utf-8"))
        except UnicodeDecodeError:
            return parse_text_recipients(file_bytes.decode("latin-1"))

    raise ValueError("Unsupported list file. Use CSV, XLSX, XLS, or TXT.")


def normalize_recipients(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["email", "name"])

    renamed = df.copy()
    renamed.columns = [to_placeholder_key(column) or f"column{idx + 1}" for idx, column in enumerate(renamed.columns)]
    renamed = renamed.fillna("")

    email_column = None
    for column in renamed.columns:
        if "email" in normalize_key(column):
            email_column = column
            break

    if email_column is None:
        for column in renamed.columns:
            if renamed[column].astype(str).str.contains("@", regex=False).any():
                email_column = column
                break

    if email_column is None:
        return pd.DataFrame(columns=["email", "name"])

    columns_set = set(renamed.columns)
    if {"firstName", "lastName"}.issubset(columns_set):
        renamed["name"] = (
            renamed["firstName"].astype(str).str.strip()
            + " "
            + renamed["lastName"].astype(str).str.strip()
        ).str.strip()
        name_column = "name"
    else:
        possible_name_columns = ["name", "fullName", "firstName", "lastName"]
        name_column = next((column for column in possible_name_columns if column in columns_set), None)

    if name_column is None:
        renamed["name"] = ""
        name_column = "name"

    renamed["email"] = renamed[email_column].astype(str).str.strip().str.lower()
    renamed["name"] = renamed[name_column].astype(str).str.strip()
    renamed = renamed[renamed["email"].str.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", na=False)]
    renamed = renamed.drop_duplicates(subset=["email"]).reset_index(drop=True)

    ordered_columns = ["email", "name"] + [column for column in renamed.columns if column not in {"email", "name"}]
    return renamed[ordered_columns]


def read_content_file(uploaded_file):
    if uploaded_file is None:
        return None, None

    file_name = uploaded_file.name.lower()
    try:
        raw_text = uploaded_file.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        raw_text = uploaded_file.getvalue().decode("latin-1")

    if file_name.endswith((".html", ".htm")):
        return "html", raw_text

    if file_name.endswith((".txt", ".md")):
        return "text", raw_text

    raise ValueError("Unsupported content file. Use TXT, HTML, HTM, or MD.")


def render_template(template_text: str, recipient: dict) -> str:
    safe_mapping = {key: str(value) for key, value in recipient.items()}
    for key in ["email", "name"]:
        safe_mapping.setdefault(key, "")
    return Template(re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", r"${\1}", template_text or "")).safe_substitute(safe_mapping)


def build_preview_html(body_text: str) -> str:
    escaped = (
        body_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"<div style='font-family:Arial,sans-serif;line-height:1.6;'>{escaped}</div>"


def send_gmail_batch(gmail_user, gmail_password, from_name, recipients_df, subject_template, body_type, body_template):
    results = []

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)

        for record in recipients_df.to_dict(orient="records"):
            try:
                subject = render_template(subject_template, record)
                rendered_body = render_template(body_template, record)

                message = MIMEMultipart("alternative")
                message["From"] = f"{from_name} <{gmail_user}>" if from_name else gmail_user
                message["To"] = record["email"]
                message["Subject"] = subject

                if body_type == "html":
                    message.attach(MIMEText(rendered_body, "html"))
                else:
                    message.attach(MIMEText(rendered_body, "plain"))
                    message.attach(MIMEText(build_preview_html(rendered_body), "html"))

                server.sendmail(gmail_user, record["email"], message.as_string())
                results.append({"email": record["email"], "status": "sent", "error": ""})
            except Exception as exc:  # noqa: BLE001
                results.append({"email": record.get("email", ""), "status": "failed", "error": str(exc)})

    return pd.DataFrame(results)


st.title("Gmail Email Bot")
st.caption("Send personalized Gmail emails from pasted lists, CSV files, or spreadsheets.")

with st.sidebar:
    st.subheader("Gmail Settings")
    default_user = os.getenv("GMAIL_USER", "")
    default_password = os.getenv("GMAIL_APP_PASSWORD", "")
    gmail_user = st.text_input("Gmail address", value=default_user, placeholder="yourgmail@gmail.com")
    gmail_password = st.text_input("Gmail app password", value=default_password, type="password")
    from_name = st.text_input("From name", placeholder="Acme Team")

    if gmail_user and gmail_password:
        st.success("Gmail credentials loaded.")
    else:
        st.warning("Add Gmail credentials here or in your .env file.")

col_left, col_right = st.columns([1.15, 0.85], gap="large")

with col_left:
    st.subheader("Recipients")
    recipient_file = st.file_uploader(
        "Upload a contact list",
        type=["csv", "xlsx", "xls", "txt"],
        help="Use CSV, Excel, or a text file with one email per line.",
    )
    raw_recipients = st.text_area(
        "Or paste recipients",
        height=200,
        placeholder="jane@example.com, Jane Doe\nmark@example.com, Mark",
    )

    recipient_sources = []
    recipient_error = ""
    try:
        if raw_recipients.strip():
            recipient_sources.append(parse_text_recipients(raw_recipients))
        if recipient_file is not None:
            recipient_sources.append(read_uploaded_recipients(recipient_file))
    except Exception as exc:  # noqa: BLE001
        recipient_error = str(exc)

    if recipient_sources:
        combined_recipients = pd.concat(recipient_sources, ignore_index=True, sort=False)
        recipients_df = normalize_recipients(combined_recipients)
    else:
        recipients_df = pd.DataFrame(columns=["email", "name"])

    st.metric("Valid recipients", len(recipients_df))
    if recipient_error:
        st.error(recipient_error)
    elif recipients_df.empty:
        st.info("Add a list manually or upload a file to preview recipients.")
    else:
        st.dataframe(recipients_df, use_container_width=True, height=260)

with col_right:
    st.subheader("Message")
    subject = st.text_input("Subject", placeholder="Hello {{name}}, a quick update")
    content_file = st.file_uploader(
        "Upload content file",
        type=["txt", "html", "htm", "md"],
        help="HTML files are sent as HTML. TXT and MD are sent as plain text.",
    )
    text_body = st.text_area(
        "Plain text content",
        height=180,
        placeholder="Hi {{name}},\n\nThanks for being on our list.",
    )
    html_body = st.text_area(
        "Optional HTML content",
        height=180,
        placeholder="<p>Hi <strong>{{name}}</strong>,</p><p>Thanks for being on our list.</p>",
    )

    uploaded_body_type = None
    uploaded_body = None
    content_error = ""
    try:
        if content_file is not None:
            uploaded_body_type, uploaded_body = read_content_file(content_file)
    except Exception as exc:  # noqa: BLE001
        content_error = str(exc)

    if html_body.strip():
        body_type = "html"
        body_template = html_body
    elif text_body.strip():
        body_type = "text"
        body_template = text_body
    elif uploaded_body:
        body_type = uploaded_body_type
        body_template = uploaded_body
    else:
        body_type = "text"
        body_template = ""

    if content_error:
        st.error(content_error)
    elif not recipients_df.empty and body_template:
        sample_record = recipients_df.iloc[0].to_dict()
        st.markdown("**Preview**")
        st.write(render_template(subject, sample_record) or "(subject is empty)")
        if body_type == "html":
            st.components.v1.html(render_template(body_template, sample_record), height=220, scrolling=True)
        else:
            st.markdown(build_preview_html(render_template(body_template, sample_record)), unsafe_allow_html=True)
    else:
        st.info("Add recipients and content to preview a personalized email.")

st.divider()
st.markdown("Use placeholders like `{{name}}`, `{{email}}`, or any spreadsheet column such as `{{company}}`.")

send_disabled = (
    bool(recipient_error)
    or bool(content_error)
    or recipients_df.empty
    or not subject.strip()
    or not body_template.strip()
    or not gmail_user
    or not gmail_password
)

if st.button("Send emails", type="primary", disabled=send_disabled, use_container_width=True):
    try:
        with st.spinner("Sending emails through Gmail..."):
            results_df = send_gmail_batch(
                gmail_user=gmail_user,
                gmail_password=gmail_password,
                from_name=from_name.strip(),
                recipients_df=recipients_df,
                subject_template=subject,
                body_type=body_type,
                body_template=body_template,
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not send emails: {exc}")
    else:
        sent_count = int((results_df["status"] == "sent").sum())
        failed_count = int((results_df["status"] == "failed").sum())

        st.subheader("Send Results")
        metric_col_1, metric_col_2 = st.columns(2)
        metric_col_1.metric("Sent", sent_count)
        metric_col_2.metric("Failed", failed_count)
        st.dataframe(results_df, use_container_width=True, height=320)
        st.download_button(
            "Download results CSV",
            results_df.to_csv(index=False).encode("utf-8"),
            file_name="send-results.csv",
            mime="text/csv",
        )
