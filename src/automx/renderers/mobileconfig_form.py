"""Static, credential-free browser form for Apple configuration profiles."""

from __future__ import annotations


def render_mobileconfig_form() -> str:
    """Return the self-contained Mobileconfig request form."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>automx Apple Mail configuration</title>
</head>
<body>
  <main>
    <h1>Apple Mail configuration</h1>
    <p>Enter the mail address and optional display name for this device.</p>
    <form action="/mobileconfig" method="post">
      <input type="hidden" name="_mobileconfig" value="true">
      <p>
        <label for="emailaddress">Mail address</label><br>
        <input id="emailaddress" name="emailaddress" type="email"
               autocomplete="email" required>
      </p>
      <p>
        <label for="cn">Display name (optional)</label><br>
        <input id="cn" name="cn" type="text" autocomplete="name">
      </p>
      <button type="submit">Download configuration profile</button>
    </form>
  </main>
</body>
</html>
"""
