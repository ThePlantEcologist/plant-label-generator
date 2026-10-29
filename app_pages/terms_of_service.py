"""Terms of Service page (served at /terms)."""

import streamlit as st

EFFECTIVE_DATE = "October 29, 2026"
CONTACT_EMAIL = "theplantecologist@gmail.com"

st.title("Terms of Service")
st.caption(f"Effective {EFFECTIVE_DATE}")

st.markdown(
    f"""
These terms cover your use of the Plant Label Generator, a free tool made by
**The Plant Ecologist**. By using the app, you agree to them. If you have
questions, email **{CONTACT_EMAIL}**.

### What the app does

The app takes plant pages from the NC State Extension Plant Toolbox and turns
them into a spreadsheet or printable Avery labels. It's free, and you can use
it without an account.

### Plant information

Plant names and care details come from the
[NC State Extension Plant Toolbox](https://plants.ces.ncsu.edu/), and you can
edit them before printing. The Plant Label Generator is an independent project.
It isn't made, endorsed, or supported by NC State University or N.C. Cooperative
Extension. Please check your labels before you rely on them, especially for
plants sold to customers or used in public gardens.

### Accounts

Accounts are by invitation only. Signing in with Google lets invited users save
settings, icons, and frequently used plants. We may add or remove invitations,
or remove saved information, at any time. You're responsible for the Google
account you sign in with.

### Your images and content

Only upload icon images you own or have permission to use. You keep all
rights to your images. By saving one, you give us permission to store it and
place it on the labels you make, and for nothing else. Please don't upload
anything illegal, hateful, or that infringes on someone else's rights.

### Fair use of the app

Please don't use the app in ways that could harm it or others. That includes
trying to get into accounts or data that aren't yours, overloading the app or
the Plant Toolbox with automated or excessive requests, or using the app to
break the law.

### Printing

Printers vary, so labels may need a small alignment adjustment. Use the
alignment test page before printing a full batch. We aren't responsible for
label sheets, ink, or materials used in printing.

### No warranty

The app is provided free and "as is." We do our best to keep it working and
accurate, but we can't promise it will always be available, error-free, or
that plant information will be complete or current. We may change or stop
the app at any time.

### Limitation of liability

To the fullest extent the law allows, The Plant Ecologist isn't liable for
any indirect or consequential damages, or for any loss from using the app,
including mislabeled plants, misprinted labels, or lost saved settings.

### Privacy

Our [Privacy Policy](/privacy) explains what information the app uses and saves.

### Changes to these terms

If we change these terms, we'll update them here and change the effective
date at the top. Using the app after a change means you accept the new terms.

### Governing law

These terms are governed by the laws of the State of North Carolina.

### Contact

**{CONTACT_EMAIL}**
"""
)

st.divider()
st.page_link("app_pages/label_tool.py", label="Back to the Label Generator", icon="🌿")
