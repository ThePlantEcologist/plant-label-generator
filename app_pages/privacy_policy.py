"""Privacy Policy page (served at /privacy)."""

import streamlit as st

EFFECTIVE_DATE = "October 29, 2026"
CONTACT_EMAIL = "theplantecologist@gmail.com"

st.title("Privacy Policy")
st.caption(f"Effective {EFFECTIVE_DATE}")

st.markdown(
    f"""
The Plant Label Generator is a free tool made by **The Plant Ecologist**. It turns
plant pages from the NC State Extension Plant Toolbox into printable labels.
This page explains what information the app uses, what it saves, and how you
can have it deleted. If you have questions, email **{CONTACT_EMAIL}**.

### Using the app without an account

You can use every labeling feature without signing in. When you do:

- The app looks up the Plant Toolbox links you paste and uses that plant
  information to build your labels.
- Any edits you make, any icon image you upload, and the PDF or CSV you
  download are handled only while you're using the app. We don't save them.

### Signing in with Google

Signing in is optional and only saves anything for people we've invited.
When you sign in, Google shares your name, email address, and profile picture
with the app. We never see your Google password, and the app doesn't ask for
access to your Gmail, Drive, contacts, or anything else in your Google account.

- We use your **email address** to check whether you're on the invite list
  and to connect you to your saved settings.
- We use your **name** only to show who is signed in. We don't store your
  name or profile picture.

If your email isn't on the invite list, nothing about you is saved, and you
can keep using the app the same way a guest does.

### What we save for invited accounts

If you're invited and signed in, the app saves:

- your email address
- your label settings, like template, font, text sizes, labels per plant,
  print alignment, and which icon you chose
- up to two icon images you choose to save
- the Plant Toolbox links you load, with the plant names, how many times
  you've loaded each one, and when you last did, so your most-used plants
  can appear in the sidebar

We don't save the plant tables you edit or the labels you generate.

### Who handles the information

We use a few service providers to run the app. They handle information only
to provide their service to us:

- **Streamlit Community Cloud** (Snowflake) hosts the app. Like most web
  hosts, it may keep technical logs such as IP addresses and browser details.
- **Supabase** stores the saved information for invited accounts.
- **Google** provides the sign-in.
- The **NC State Extension Plant Toolbox** receives the plant page requests
  the app makes when you load links. No personal information is sent.

We don't sell your information, use it for advertising, or share it with
anyone else unless the law requires it.

### Cookies

When you sign in, the app sets a cookie that keeps you signed in. We don't use
advertising or tracking cookies. The hosting platform may use cookies it needs
to run the app.

### Keeping and deleting your information

We keep saved information for as long as you have an invited account. You can
delete your saved icons and remove plants from your Frequent plants list at
any time in the app. To have everything deleted, email **{CONTACT_EMAIL}** and
we'll remove it, normally within 30 days. If you're removed from the invite
list, we delete your saved information.

### Keeping it secure

Saved information is kept in a private database and private file storage that
only the app can reach. No system is perfectly secure, but we take reasonable
steps to protect what we store.

### Google user data

The app's use of information received from Google follows the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including its Limited Use requirements.

### Children

The app isn't meant for children under 13, and we don't knowingly collect
information from them. If you think a child has given us information, email
us and we'll delete it.

### Changes to this policy

If we change this policy, we'll update it here and change the effective date
at the top.

### Contact

Questions or deletion requests: **{CONTACT_EMAIL}**
"""
)

st.divider()
st.page_link("app_pages/label_tool.py", label="Back to the Label Generator", icon="🌿")
