# WHOZ Data Extraction

Extract talent data, profiles, certifications, accreditations, and photos from the [WHOZ](https://www.whoz.com) API.

## Project Structure

```
.
├── .env                                # API credentials & config
├── requirements.txt                    # Python dependencies
├── ingestion/
│   ├── whoz_client.py                  # Reusable API client (auth, pagination)
│   ├── extract_talents_and_profiles.py # Extract talents, profiles, certs, accreditations
│   └── extract_photos.py              # Download talent photos
├── processing/
│   └── build_summaries.py             # Transform raw data into app-ready summaries
└── data/                               # Output (generated)
    ├── all.json                        # Combined summaries for all people
    └── <email>/
        ├── <email>.json                # Raw talent record
        ├── summary.json                # App-ready summary
        ├── <photo-uid>.jpg             # Profile photo
        ├── profiles/
        │   └── <profile-name>.json
        ├── certifications/
        │   └── <cert-name>.json
        └── accreditations/
            └── <accreditation-name>.json
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a `.env` file

```env
# Environment variables for WHOZ API integration
WHOZ_API_URL="https://www.whoz.com/"
WHOZ_TOKEN_PATH="auth/realms/whoz/protocol/openid-connect/token"
WHOZ_CLIENT_ID=""
WHOZ_CLIENT_SECRET=""
WHOZ_GRANT_TYPE="client_credentials"
WHOZ_WORKSPACE_ID=""
WHOZ_FEDERATION_ID=""
```

Fill in `WHOZ_CLIENT_ID`, `WHOZ_CLIENT_SECRET`, `WHOZ_WORKSPACE_ID`, and `WHOZ_FEDERATION_ID` with your credentials.

### 3. Load environment variables

Before running any script, load your `.env`:

```bash
source .env
```


## Usage

Run scripts in this order:

### Step 1 — Extract raw data

```bash
python ingestion/extract_talents_and_profiles.py
```

Fetches all talents, profiles, certifications, and accreditations from the WHOZ API. Saves raw JSON into `data/<email>/`.

### Step 2 — Download photos

```bash
python ingestion/extract_photos.py
```

Fetches the talent list again independently, then downloads each person's photo to `data/<email>/<photo-uid>.jpg`.

Safe to re-run — skips already-downloaded photos.

### Step 3 — Build summaries

```bash
python processing/build_summaries.py
```

Reads raw data from `data/`, transforms it into a flat app-ready format, and writes:
- `data/<email>/summary.json` — individual summary per person
- `data/all.json` — combined array of all summaries

## Summary Schema

Each `summary.json` (and each entry in `all.json`) has this shape:

```json
{
  "name": "string",
  "firstName": "string",
  "lastName": "string",
  "email": "string",
  "phone": "string",
  "photo": "string",
  "initials": "string",
  "gender": "string",
  "nationalities": ["string"],
  "language": "string",
  "bio": "string",
  "hobbies": ["string"],
  "location": {
    "city": "string",
    "country": "string",
    "formatted": "string",
    "lat": "number",
    "lng": "number"
  },
  "remote": "boolean",
  "team": "string",
  "scope": "string",
  "manager": { "id": "string", "name": "string", "email": "string" },
  "mentor": { "id": "string", "name": "string", "email": "string" },
  "mobility": {
    "national": "boolean",
    "international": "boolean",
    "destinations": [{ "city": "string", "countryCode": "string", "formattedAddress": "string" }]
  },
  "jobTitle": "string",
  "company": "string",
  "aim": "string",
  "yearsOfExperience": "number",
  "topSkills": [{ "name": "string", "type": "string", "proficiency": "number", "highlighted": "boolean" }],
  "experience": [{ "title": "string", "company": "string", "description": "string", "startDate": "string", "endDate": "string", "current": "boolean", "location": "string" }],
  "education": [{ "school": "string", "degree": "string", "description": "string", "startDate": "string", "endDate": "string", "location": "string" }],
  "certifications": [{ "title": "string", "issuer": "string", "obtainedDate": "string", "expirationDate": "string" }],
  "accreditations": [{ "title": "string", "issuer": "string", "obtainedDate": "string", "expirationDate": "string", "description": "string" }]
}
```

## Key Notes

- **Scope filtering:** Use the `scope` field to identify active employees (`EMPLOYEE`) vs alumni (`ALUMNI`), freelancers (`FREELANCE`), or candidates (`CANDIDATE`).
- **Photo linking:** The `photo` field in summaries contains the UID. The file is stored as `data/<email>/<uid>.jpg`.
- **Pagination:** The WHOZ API returns paginated results. All scripts handle this automatically via the `paginate_list()` method in `whoz_client.py`.
- **Batching:** Profile, certification, and accreditation endpoints are called in batches of ≤50 talent IDs per request (WHOZ API limit).
- **Idempotent:** Photo downloads skip existing files. Re-running extraction will overwrite JSON files with fresh data.
