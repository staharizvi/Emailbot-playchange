# Gmail Email Bot

A Python + Streamlit app for sending personalized Gmail emails from:

- pasted recipient lists
- uploaded `.csv`, `.xlsx`, `.xls`, or `.txt` files
- typed message content or uploaded `.txt`, `.html`, `.htm`, or `.md` files

It supports placeholders like `{{name}}`, `{{email}}`, and any spreadsheet column such as `{{company}}`.

## Features

- Streamlit interface
- Gmail sending with an App Password
- CSV and Excel recipient imports
- Uploaded or typed email content
- Recipient preview before sending
- Personalized subject/body placeholders
- Send results table with CSV export

## Setup

1. Create and activate a virtual environment if you want one.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment file:

```bash
cp .env.example .env
```

4. Add your Gmail credentials:

```env
GMAIL_USER=yourgmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

5. Run the app:

```bash
streamlit run app.py
```

## Gmail Setup

1. Turn on 2-Step Verification in your Google account.
2. Create a Gmail App Password.
3. Put that password into `GMAIL_APP_PASSWORD`.

## Recipient Formats

### Paste recipients

```text
jane@example.com, Jane Doe
mark@example.com, Mark
```

You can also paste one email per line.

### CSV or spreadsheet

Recommended columns:

```text
email,name,company
```

or

```text
email,firstName,lastName,company
```

## Personalization

Use placeholders in the subject or body:

```text
Subject: Hello {{name}}
Body: Hi {{name}}, thanks for checking out {{company}}.
```

Any uploaded spreadsheet column becomes available as a placeholder.

## Notes

- Gmail may rate-limit large sending batches.
- HTML content takes priority over plain text.
- Markdown files are treated as plain text.
