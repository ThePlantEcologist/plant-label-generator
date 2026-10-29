# Setting up sign-in and saved settings

The app works for everyone without an account. These steps turn on the
optional **Sign in with Google** button for people you invite. Invited users
get saved settings, two saved label icons, and a "Frequent plants" sidebar.

Plan on about 30 minutes. You only do this once.

You'll set up three things:

1. **Supabase** stores the invite list, settings, icons, and plant counts.
2. **Google Cloud** provides the "Sign in with Google" button.
3. **Streamlit and GitHub secrets** connect them to the app.

Anything marked *secret* below should only ever be pasted into Streamlit's
Secrets box or GitHub's Secrets page. Never commit it to the repo.

---

## 1. Supabase

1. Go to https://supabase.com, sign in, and create a **New project** on the
   free plan. Pick a region in the US East. Save the database password
   somewhere safe (the app doesn't use it, but you may need it someday).
2. When the project is ready, open **SQL Editor > New query**, paste in the
   entire contents of `supabase_setup.sql`, and click **Run**.
3. Invite people. In **SQL Editor**, run this with real Google account
   emails, all lowercase:

   ```sql
   insert into public.invited_users (email, note) values
     ('your.google.account@gmail.com', 'owner')
   on conflict (email) do nothing;
   ```

   To invite someone later, run the same thing with their email. You can
   also use **Table Editor > invited_users > Insert row**. To remove
   someone, delete their row; their saved settings and plant list go with it
   (icons stay in storage until you delete them from **Storage > label-icons**).
4. Open **Project Settings > API Keys** and copy:
   - **Project URL** (looks like `https://abcd1234.supabase.co`)
   - **Publishable key** (starts with `sb_publishable_`)
   - **Secret key** (starts with `sb_secret_`). *Secret.*

   If you only see "anon" and "service_role" keys, click to create the new
   publishable and secret keys. Supabase is retiring the old ones.

## 2. Google sign-in

1. Go to https://console.cloud.google.com and create a project (for example,
   "Plant Label Generator").
2. Open **Google Auth Platform** (or **APIs & Services > OAuth consent screen**):
   - App name: Plant Label Generator
   - User support email and developer contact: your email
   - Audience: **External**
   - Data access / scopes: leave the defaults (just email, profile, openid).
   - Under **Audience**, click **Publish app**. Because the app only asks
     for basic profile info, Google doesn't require a review. (If you leave it
     in "Testing," only people you also add as Google test users can sign in.)
3. Open **Clients** (or **Credentials > Create credentials > OAuth client ID**):
   - Application type: **Web application**
   - Authorized redirect URIs, add both:
     - `https://YOUR-APP-NAME.streamlit.app/oauth2callback`
     - `http://localhost:8501/oauth2callback`
   - Click **Create** and copy the **Client ID** and **Client secret**
     (*secret*).

## 3. Connect the app

### Streamlit secrets

1. Make a random cookie secret. In Terminal, run:
   `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. In Streamlit Community Cloud, open your app's **Settings > Secrets** and
   paste this, filling in your values:

   ```toml
   [auth]
   redirect_uri = "https://YOUR-APP-NAME.streamlit.app/oauth2callback"
   cookie_secret = "THE RANDOM STRING FROM STEP 1"
   client_id = "FROM GOOGLE"
   client_secret = "FROM GOOGLE"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

   [supabase]
   url = "https://YOUR-PROJECT.supabase.co"
   secret_key = "sb_secret_..."
   ```

3. Save. The app restarts, and **Sign in with Google** appears in the sidebar.

The same template is in `.streamlit/secrets.toml.example`. For testing on your
computer, copy it to `.streamlit/secrets.toml` (git ignores that file) and use
the `localhost` redirect URI.

### Keep Supabase from pausing

Free Supabase projects pause after about a week with no database activity.
The included GitHub Action (`.github/workflows/supabase-keepalive.yml`)
pings the database every 2 days so that never happens, even during slow
months. It uses only the publishable key, which can do nothing except
update a timestamp.

1. In GitHub, open the repo's **Settings > Secrets and variables > Actions >
   New repository secret** and add:
   - `SUPABASE_URL` = your Project URL
   - `SUPABASE_PUBLISHABLE_KEY` = your `sb_publishable_` key
2. Open the **Actions** tab, choose **Supabase keep-alive**, and click
   **Run workflow** to test it. A green check means it worked.

GitHub normally switches off scheduled jobs in repos that go 60 days without
a commit. The workflow re-enables itself each run to prevent that.

**Safety net:** if it ever does pause, Supabase emails you first, and a paused
project can be restored with one click (**Resume project** in the dashboard)
for up to a year with all data intact.

---

## What changed in the app

- **Label margins:** Avery 5160 / 5520 / 5260 now use the official layout
  (2⅝" x 1" labels, 3/16" side margins, 1/8" gap between columns, 1/2" top).
  The old layout stretched each label to about 2.67" wide, so text crept
  past the right-hand labels.
- **Print alignment:** in the PDF options, **Print alignment** lets you
  download a test page, nudge everything left/right or up/down to match your
  printer, and set how much blank border each label keeps. Signed-in users
  get their nudge saved.
- **Sign in (optional):** invited Google accounts get saved settings
  (template, font, sizes, labels per plant, output format, nudge, icon
  choice), two saved icons, and a Frequent plants list. Uninvited accounts
  and guests can still use everything; nothing is saved for them.
