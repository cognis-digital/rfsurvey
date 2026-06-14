# Integrations

**rfsurvey** plugs into your stack through [`cognis-connect`](https://github.com/cognis-digital/cognis-connect),
the suite's integration SDK. It maps any tool's JSON into a canonical **Finding** and
forwards it to the platforms that fit the **General OSINT / security tool** domain.

```bash
pip install "git+https://github.com/cognis-digital/cognis-connect.git"
```

## Forward findings to a platform

Once `rfsurvey` emits JSON findings, pipe them straight to a destination — `--dry-run`
previews the exact request without sending:

```bash
rfsurvey ... --format json | cognis-connect emit --to stix   # STIX 2.1 bundle
rfsurvey ... --format json | cognis-connect emit --to slack --url $URL --token $TOK   # Slack
rfsurvey ... --format json | cognis-connect emit --to webhook --url $URL --token $TOK   # generic webhook
```

Recommended for this domain: **stix, slack, webhook**. The full set is
`stix · taxii · misp · sigma · splunk · elastic · slack · discord · webhook · brief`.

## From Python

`normalize()` maps any record (field/indicator aliases handled) into a `Finding`, so this
works whatever `rfsurvey` outputs:

```python
from cognis_connect import normalize, stix
findings = [normalize(rec, source="rfsurvey") for rec in records]   # records = your JSON output
print(stix.to_bundle(findings))
```

## Other channels

- **AI enrichment / summaries** — point add-ins at an [`edgemesh`](https://github.com/cognis-digital/edgemesh)
  `/v1` gateway (`OPENAI_BASE_URL`); `cognis-connect emit --to brief` writes an analyst summary.
- **Composition patterns & reference stacks** — see [INTEROP.md](INTEROP.md).

> Integration backbone for the 300+ suite. **[github.com/cognis-digital](https://github.com/cognis-digital)**
