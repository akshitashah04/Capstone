# Connect this site to Google Books

The deployed app queries Google's official Volumes API through its server. The missing project configuration is a Google Books API key. Connecting Google Drive does not supply a Google Cloud project API key or Books API quota.

## Google Cloud setup

1. Open https://console.cloud.google.com/ and select or create the project that will own this capstone's API quota.
2. Open https://console.cloud.google.com/apis/library/books.googleapis.com and enable **Books API** in that project.
3. Open https://console.cloud.google.com/apis/credentials and create an API key.
4. Restrict the key's allowed APIs to **Books API**. This application calls Google from a server, so a key restricted to browser HTTP referrers will not work for the server proxy. Use the application restriction appropriate to the chosen hosting infrastructure; Cloudflare serverless egress does not provide a single fixed project IP by default.
5. Review the project's Books API quotas and configure appropriate limits. Do not assume unlimited access.

## Host configuration

Store the key in this Site's production environment configuration:

- Name: `GOOGLE_BOOKS_API_KEY`
- Type: secret
- Value: the newly created key

Do not paste the key into a public page, a GitHub issue, browser code, the hosting manifest, or chat. Do not use a `VITE_` prefix. Do not commit it to GitHub. Local `.env` files are not automatically read or sent to production.

After the secret is configured, redeploy the saved Site version so the new runtime environment revision takes effect. This does not require changing the site's public-access setting or introducing a login screen.

For local development, set the variable through the terminal/environment secret facility before starting `npm run serve`; avoid putting its literal value in shell history.

## Verify the connection

1. Open the site's `/api/status` endpoint. `apiKeyConfigured` should be true. This only verifies configuration, not a successful Google request.
2. Search for a specific title, ISBN, and a broader topic such as `stock market wall street new york` with Collection set to Google Books.
3. Confirm the request to `/api/books` returns Google `items`, and that the displayed records have original Google Books links.
4. Check that the API response, HTML, JavaScript, and browser Network panel do not contain the API key. The browser calls this site's proxy; the server adds the key only on its outbound Google request.

The app attempts public requests without a key and can try a direct public request from the visitor's browser when the unkeyed server request is rejected. Google may refuse or rate-limit both. This fallback is not a substitute for project-owned quota and never displays fabricated Google Books results.

## Diagnosing failures

| Code | Action |
| --- | --- |
| `API_KEY_REQUIRED` | Add a project key to the production secret. |
| `INVALID_API_KEY` | Replace the key with an active key from the intended project. |
| `BOOKS_API_DISABLED` | Enable Books API in the key's Google Cloud project. |
| `API_KEY_RESTRICTED` | Check that API/application restrictions permit the server request. |
| `QUOTA` | Review Google Cloud quota; wait for reset or adjust the project's approved limits. |
| `NETWORK` | Check hosting connectivity and retry when the provider is reachable. |

The public API returns only safe diagnostic codes and configuration flags. It never echoes the Google error message or the key. Server diagnostic logs omit query text and credentials.
