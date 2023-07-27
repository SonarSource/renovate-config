# re-renovate
Renovate presets

The renovate app must be enabled for the repository and configured on the default branch using `.github/renovate.json`:
```json
{
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "extends": [
        "github>SonarSource/renovate-config:re-team"
    ]
}
```

## re-team

Updates github-actions and AWS AMIs provided by the Internal Security Team.

## languages-team

Replaces version strings in `snapshot-generation.sh`.

```bash
# renovate: datasource=<data-source-name> depName=<repository-name>
export <NAME>_VERSION=<version>
```
Where:
- `data-source-name`: the renovate datasource. Use github-releases
- `repository-name`: github owner/repo name to check for new releases
- `NAME`: use a descriptive variable name for storing the release version
- `version`: version number to use and check updates for in the format of `MAJOR.MINOR.PATCH.BUILD`

Example:
```bash
# renovate: datasource=github-releases depName=SonarSource/sonar-kotlin
export KOTLIN_VERSION=2.15.0.2579
```
